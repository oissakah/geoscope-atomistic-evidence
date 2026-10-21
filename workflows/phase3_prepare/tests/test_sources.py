"""CPU fixtures for grouping, bounded batches and coordinate-only measurement."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes
from ase.constraints import FixAtoms
from ase.io import read, write

from geomscope import data, uma
from phase3 import sources


class ZeroForceFixture(Calculator):
    """Explicit analytic test fixture, never a substitute physical calculator."""
    implemented_properties = ["energy", "forces"]
    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        self.results = dict(energy=0., forces=np.zeros((len(atoms),3)))


def fixture_atoms():
    atoms = Atoms("Cu5COH", positions=[[1,1,1],[5,1,1],[1,5,1],[5,5,1],
                  [3,3,2],[3,3,4],[4.2,3,4],[2.2,3.5,4]], cell=[15,15,15], pbc=True)
    atoms.set_tags([0,0,0,0,1,2,2,2])
    atoms.set_constraint(FixAtoms(indices=[0,1,2,3]))
    return atoms


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.out = self.base / "result"
        self.out.mkdir()
        self.config = dict(n_systems=60, seed=20261021, max_atoms=180, min_adsorbate_atoms=3,
                           max_steps=600, fmax=.05, anchor_max_displacement_A=.02)

    def frozen(self, n=60):
        initial = self.out / "inputs" / "initial.extxyz"
        initial.parent.mkdir(exist_ok=True)
        write(initial, fixture_atoms(), write_results=False)
        selected=[]
        for i in range(n):
            selected.append(dict(pair_id=f"pair_{i}", system_id=f"9_{i}_2", group_id=f"9_{i}_2", config_id="rand0",
                initial_path=str(initial), initial_sha256=data._sha256(initial),
                source_member=f"ase_val_inputs/9_{i}_2_rand0.traj", source_sha256="a"*64,
                mobile_indices=[4,5,6,7], adsorbate_indices=[5,6,7], anchor_indices=[0,1,2,3],
                adsorbate_bonds=sources._bonds(fixture_atoms(),[5,6,7]), split=sources.SPLIT,
                topology_reviewed=False))
        sources._save(self.out/"selection.json", dict(status="COMPLETE",selection=selected))
        sources._save(self.out/"model_manifest.json", dict(test_only=True))
        return selected

    def record(self, selected, *, converged=True, transform=None):
        folder=self.out/"batches"/selected["pair_id"]
        folder.mkdir(parents=True,exist_ok=True)
        a=read(selected["initial_path"])
        b=a.copy()
        b.positions[selected["adsorbate_indices"]] += [.2,0,0]
        if transform:
            transform(b)
        initial,final=folder/"initial.extxyz",folder/"final.extxyz"
        write(initial,a,write_results=False)
        write(final,b,write_results=False)
        log,traj=folder/"optimizer.log",folder/"optimizer.traj"
        log.write_text("analytic fixture only\n")
        traj.write_bytes(b"analytic test placeholder; not read as trajectory")
        paths=dict(initial=initial,final=final,optimizer_log=log,trajectory=traj)
        return dict(**selected,selection=copy.deepcopy(selected),
                    **{k+"_path":str(v) for k,v in paths.items() if k!="initial"},
                    source_initial_sha256=selected["initial_sha256"],converged=converged,
                    status="converged" if converged else "nonconverged",steps=10,
                    final_fmax_eV_A=.01 if converged else .2,
                    artifacts={k:dict(path=str(v),sha256=data._sha256(v)) for k,v in paths.items()}) | {"initial_path":str(initial)}

    def test_fixed_disjoint_batches_have_no_replacement(self):
        selected=self.frozen()
        observed=[]
        def relax(items,manifest,out,**kwargs):
            observed.extend(items)
            self.assertEqual(kwargs["steps"],600)
            self.assertEqual(kwargs["smoke_systems"],3)
            self.assertFalse(kwargs["smoke_only"])
            return [dict(pair_id=x["pair_id"],status="error") for x in items]
        with patch.object(sources,"relax_selected",side_effect=relax) as call:
            for index in range(3):
                rows=sources.run_batch(self.out,index,self.config)
                self.assertEqual(len(rows),20)
                self.assertTrue(all(r["status"]=="error" for r in rows))
        self.assertEqual([r["pair_id"] for r in observed],[r["pair_id"] for r in selected])
        self.assertEqual(len({r["pair_id"] for r in observed}),60)
        self.assertEqual(call.call_count,3)

    def test_foreign_batch_membership_is_rejected(self):
        self.frozen()
        with patch.object(sources,"relax_selected",return_value=[dict(pair_id="foreign")]):
            with self.assertRaisesRegex(ValueError,"membership"):
                sources.run_batch(self.out,0,self.config)

    def test_missing_batches_retain_all_sixty_sources(self):
        self.frozen()
        result=sources.measure_sources(self.out,self.config)
        self.assertEqual(result["outcome_denominator"],60)
        self.assertEqual(result["outcome_counts"],{"missing_batch_summary_attempt_status_unknown":60})
        self.assertEqual(result["excluded_source_endpoints"],60)
        self.assertEqual(result["measured_pairs"],0)
        self.assertFalse(result["gold_labels_created"])

    def test_coordinate_metrics_and_control_use_different_references(self):
        selected=self.frozen(n=1)
        config=dict(self.config,n_systems=1)
        entry=self.record(selected[0])
        sources._save(self.out/"batch_0_records.json",[entry])
        result=sources.measure_sources(self.out,config)
        self.assertEqual(result["measured_pairs"],1)
        self.assertEqual(result["synthetic_pairs"],1)
        pairs=[json.loads(x) for x in (self.out/"pair_measurements.jsonl").read_text().splitlines()]
        real,control=pairs
        self.assertAlmostEqual(real["measurements"]["adsorbate_frame_rmsd_A"],.2,places=7)
        self.assertAlmostEqual(control["measurements"]["adsorbate_frame_rmsd_A"],.7,places=7)
        self.assertAlmostEqual(control["measurements"]["internal_rmsd_A"],0,places=10)
        self.assertAlmostEqual(control["measurements"]["mobile_rmsd_A"],.7*np.sqrt(3/4),places=7)
        self.assertEqual(control["provenance"]["source_hashes"]["initial"],data._sha256(Path(entry["final_path"])))
        self.assertEqual(real["split"],"protected_candidate")
        self.assertFalse(control["energetic_or_convergence_claims_enabled"])
        self.assertFalse(real["topology_reviewed"])
        self.assertFalse(list(self.out.glob("*gold*")))
        self.assertFalse(list(self.out.glob("*cases*")))

    def test_nonconvergence_is_not_replaced(self):
        selected=self.frozen(n=1)
        sources._save(self.out/"batch_0_records.json",[self.record(selected[0],converged=False)])
        result=sources.measure_sources(self.out,dict(self.config,n_systems=1))
        self.assertEqual(result["outcome_counts"],{"nonconverged":1})
        self.assertEqual(result["measured_pairs"],0)
        self.assertEqual(result["outcome_denominator"],1)

    def test_changed_final_tags_fail_closed(self):
        selected=self.frozen(n=1)
        def corrupt(atoms):
            tags=atoms.get_tags();tags[4]=2;atoms.set_tags(tags)
        sources._save(self.out/"batch_0_records.json",[self.record(selected[0],transform=corrupt)])
        result=sources.measure_sources(self.out,dict(self.config,n_systems=1))
        self.assertEqual(result["measured_pairs"],0)
        rejection=json.loads((self.out/"measurement_rejections.json").read_text())[0]
        self.assertIn("tags",rejection["reason"])

    def test_changed_bond_graph_rejected(self):
        selected=self.frozen(n=1)
        def break_graph(atoms):
            atoms.positions[7] += [5,0,0]
        sources._save(self.out/"batch_0_records.json",[self.record(selected[0],transform=break_graph)])
        result=sources.measure_sources(self.out,dict(self.config,n_systems=1))
        self.assertEqual(result["measured_pairs"],0)
        self.assertIn("bond graphs",json.loads((self.out/"measurement_rejections.json").read_text())[0]["reason"])

    def test_corrupted_endpoint_artifact_rejected(self):
        selected=self.frozen(n=1)
        entry=self.record(selected[0]);Path(entry["final_path"]).write_text("changed")
        sources._save(self.out/"batch_0_records.json",[entry])
        result=sources.measure_sources(self.out,dict(self.config,n_systems=1))
        self.assertEqual(result["measured_pairs"],0)
        self.assertIn("artifact",json.loads((self.out/"measurement_rejections.json").read_text())[0]["reason"])

    def test_phase3_saved_error_resumes_without_retry(self):
        checkpoint=self.base/"record.json"
        item=dict(pair_id="A",source_sha256="a"*64,selection={"test_only":True})
        settings={"steps_cap":600}
        hashes=dict(settings_sha256=uma._hash_json(settings))
        entry=dict(pair_id="A",source_initial_sha256="a"*64,selection=item["selection"],
                   settings=settings,status="error",run_signature="signature",artifacts={},**hashes)
        sources._save(checkpoint,entry)
        resumed=uma._resume_record(checkpoint,"signature",hashes,item)
        self.assertEqual(resumed["status"],"error")
        self.assertTrue(resumed["resumed"])

    def test_missing_batch_summary_recovers_verified_finalized_records(self):
        selected=self.frozen()
        completed=self.record(selected[0])
        seen=[]
        def finalized(path,signature,hashes,item):
            seen.append((path,signature,hashes,item))
            return completed if item["pair_id"]==selected[0]["pair_id"] else None
        # _recover_batch checks the expected record location before invoking the
        # strict verifier, so make these candidate paths visible for this mock.
        with patch.object(Path,"is_file",return_value=True),patch.object(data,"_sha256",return_value=selected[0]["initial_sha256"]), \
             patch.object(uma,"_resume_record",side_effect=finalized):
            recovered=sources._recover_batch(self.out,0,selected[:20],self.config)
        self.assertEqual(len(recovered),20)
        self.assertTrue(recovered[0]["recovered_from_finalized_checkpoint"])
        self.assertEqual(recovered[0]["status"],"converged")
        self.assertEqual(sum(r["status"]=="unverified_finalized_record" for r in recovered),19)
        self.assertEqual(len(seen),20)
        self.assertTrue(all(s[2]["settings_sha256"] for s in seen))

    def test_recovery_matches_real_cpu_generated_uma_record_identity(self):
        selected=self.frozen(n=1)
        config=dict(self.config,n_systems=1)
        manifest=dict(model_name="uma-s-1p2p1",repo_id="facebook/UMA",revision="a"*40,files={})
        sources._save(self.out/"model_manifest.json",manifest)
        with patch.object(uma,"_check_model"),patch.object(uma,"_create_runtime",
                return_value=(ZeroForceFixture,dict(test_only=True,device="CPU_ANALYTIC_FIXTURE"))):
            records=uma.relax_selected(selected,manifest,self.out/"batches"/"batch_0",seed=config["seed"],
                                        fmax=config["fmax"],steps=600,smoke_systems=3,smoke_only=False)
        self.assertEqual(records[0]["status"],"converged")
        self.assertFalse((self.out/"batch_0_records.json").exists())
        with patch.object(uma,"_create_runtime") as runtime:
            result=sources.measure_sources(self.out,config)
        runtime.assert_not_called()
        self.assertEqual(result["measured_pairs"],1)
        audit=json.loads((self.out/"batch_recovery_audit.json").read_text())
        self.assertEqual(audit[0]["recovered_finalized_records"],1)
        recovered=json.loads((self.out/"relaxation_results.json").read_text())[0]
        self.assertEqual(recovered["run_signature"],records[0]["run_signature"])
        self.assertTrue(recovered["recovered_from_finalized_checkpoint"])

    def test_interrupted_partial_attempt_is_not_overwritten_or_retried(self):
        selected=self.frozen(n=1)
        partial=[]
        def interrupted(checkpoint,*args):
            checkpoint.parent.mkdir(parents=True,exist_ok=True)
            artifact=checkpoint.parent/"optimizer.traj"
            artifact.write_bytes(b"partial trajectory retained verbatim")
            partial.append(artifact)
            return None
        manifest=dict(model_name="uma-s-1p2p1",repo_id="facebook/UMA",revision="a"*40,files={})
        with patch.object(uma,"_check_model"),patch.object(uma,"_resume_record",side_effect=interrupted), \
             patch.object(uma,"_create_runtime") as runtime:
            with self.assertRaisesRegex(ValueError,"interrupted attempt"):
                uma.relax_selected(selected,manifest,self.out/"batch",steps=600)
        runtime.assert_not_called()
        self.assertEqual(partial[0].read_bytes(),b"partial trajectory retained verbatim")
        self.assertFalse((partial[0].parent/"record.json").exists())

    def prepare_mocks(self,members,excluded,select_fn):
        archive=self.base/"archive.tar.gz";archive.write_bytes(b"test")
        return patch.multiple(data,_download_pinned_archive=lambda cache:archive,
                    ARCHIVE_BYTES=4,_sha256=lambda path:"a"*64,ARCHIVE_SHA256="a"*64,
                    _safe_extract_archive=lambda archive,cache:members,_select_initials=select_fn)

    def test_exclusions_happen_before_selection(self):
        members=[dict(system_id=f"g{i%200}",source_member=f"member{i}",source_sha256="b"*64,config_id="rand0")
                 for i in range(15256)]
        excluded={f"g{i}" for i in range(20)}
        seen=[]
        def selector(candidates,out,n,seed,max_atoms,min_ads,dataset):
            seen.extend(candidates)
            self.assertFalse(excluded & {x["system_id"] for x in candidates})
            selected=self.frozen()
            for i,row in enumerate(selected):
                row["group_id"]=row["system_id"]=f"g{i+20}"
            sources._save(out/"selection.json",dict(status="COMPLETE",selection=selected,selected_systems=60))
            return selected
        with self.prepare_mocks(members,excluded,selector),patch.object(sources,"_inventory",return_value={}):
            chosen=sources.prepare_sources(self.base/"cache",self.out,excluded,self.config)
        self.assertEqual(len(chosen),60)
        self.assertEqual(len({x["group_id"] for x in chosen}),60)
        split=json.loads((self.out/"split_manifest.json").read_text())
        self.assertTrue(split["excluded_before_selection"])
        self.assertEqual(split["excluded_groups"],sorted(excluded))
        self.assertIsNotNone(split["selection_identity_sha256"])
        self.assertTrue(all(x["split"]=="protected_candidate" for x in chosen))

    def test_insufficient_eligible_preserves_diagnostic(self):
        members=[dict(system_id=f"g{i%200}",source_member=f"member{i}",source_sha256="b"*64,config_id="rand0")
                 for i in range(15256)]
        excluded={"g0"}
        def selector(candidates,out,*args):
            sources._save(out/"selection.json",dict(status="INSUFFICIENT_ELIGIBLE_SYSTEMS",selection=[],selected_systems=0))
            raise data.DataPreparationError("synthetic insufficient fixture")
        with self.prepare_mocks(members,excluded,selector):
            with self.assertRaises(data.DataPreparationError):
                sources.prepare_sources(self.base/"cache",self.out,excluded,self.config)
        split=json.loads((self.out/"split_manifest.json").read_text())
        self.assertEqual(split["status"],"INSUFFICIENT_ELIGIBLE_SYSTEMS")
        self.assertEqual(split["selected_systems"],0)
        self.assertTrue((self.out/"candidate_membership.json").is_file())

    def test_deterministic_grouped_selection_with_analytic_fixture(self):
        members=[dict(system_id=f"g{i}",config_id=f"rand{j}",path="not_read",source_member=f"g{i}_rand{j}.traj",source_sha256="a"*64)
                 for i in range(5) for j in range(2)]
        atoms=fixture_atoms()
        prepared=(atoms,[4,5,6,7],[5,6,7],[0,1,2,3],sources._bonds(atoms,[5,6,7]))
        dataset=dict(source_archive_sha256="b"*64,origin="ANALYTIC_TEST_ONLY")
        with patch.object(data,"_initial_structure",return_value=prepared):
            one=data._select_initials(members,self.out/"one",3,101,180,3,dataset)
            two=data._select_initials(list(reversed(members)),self.out/"two",3,101,180,3,dataset)
        self.assertEqual([(x["group_id"],x["config_id"]) for x in one],[(x["group_id"],x["config_id"]) for x in two])
        self.assertEqual(len({x["group_id"] for x in one}),3)


if __name__=="__main__":
    unittest.main()
