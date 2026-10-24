"""Read-only inventory of official OC20 tar. Never extracts full dataset or builds benchmark."""
from __future__ import annotations
import argparse,collections,hashlib,json,tarfile,gzip
from pathlib import Path

EXPECTED_MD5 = '5731862978d80502bbf7017d68c2c729'

def md5sum(path):
    h=hashlib.md5()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(8*1024*1024),b''):
            h.update(data)
    return h.hexdigest()

def type_name(name):
    p=name.lower()
    for suffix in ('.tar.gz','.tar.xz','.tar.bz2','.tgz','.traj.gz','.tar','.traj','.extxyz','.xyz.gz','.xyz','.zip','.lmdb','.npz','.gz','.txt','.md'):
        if p.endswith(suffix):return suffix
    return Path(p).suffix or '(none)'

def magic_name(head):
    if head.startswith(b'\x1f\x8b'):return 'gzip'
    if head.startswith(b'PK\x03\x04'):return 'zip'
    if head.startswith(b'\x89HDF'):return 'hdf5'
    if head.startswith(b'!'):return 'possibly-ASE-Ulm'
    if head.startswith(b'SQLite format 3'):return 'sqlite'
    if head.startswith(b'\x93NUMPY'):return 'npy'
    if len(head)>=262 and head[257:262]==b'ustar':return 'tar'
    if not head:return 'empty'
    return 'other'

def nested_peek(tf,member,max_entries=12):
    # Sample only a few headers; no full decompression/extraction.
    with tf.extractfile(member) as raw:
        with tarfile.open(fileobj=raw,mode='r|*') as inner:
            items=[]
            for item in inner:
                items.append({'name':item.name,'size':item.size,'type':type_name(item.name),'is_file':item.isfile()})
                if len(items)>=max_entries:break
    return items

def inspect(path,out_dir,max_nested=4,max_nested_items=12):
    path=Path(path);out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    digest=md5sum(path)
    if digest!=EXPECTED_MD5:raise ValueError(f'STOP: checksum mismatch {digest}; expected {EXPECTED_MD5}')
    entries=[];types=collections.Counter();magics=collections.Counter();nested=[];readmes=[]
    with tarfile.open(path,'r:*') as archive:
        # Random-access tar headers: does not unpack all 9.5GB of contents.
        for member in archive:
            typ=type_name(member.name);types[typ]+=1
            row={'name':member.name,'size_bytes':member.size,'type':typ,'regular_file':member.isfile()}
            if member.isfile():
                with archive.extractfile(member) as f: head=f.read(512)
                row['first_bytes_hex']=head[:16].hex()
                row['magic']=magic_name(head)
                magics[row['magic']]+=1
                if typ in ('.txt','.md') and member.size<65536 and len(readmes)<3:
                    with archive.extractfile(member) as f:
                        readmes.append({'name':member.name,'text_preview':f.read(10000).decode('utf-8','replace')})
                if len(nested)<max_nested and (typ in ('.tgz','.tar.gz','.tar','.tar.xz','.tar.bz2') or row['magic']=='gzip'):
                    try:
                        sample=nested_peek(archive,member,max_nested_items)
                        nested.append({'parent':member.name,'sample_only':True,'children':sample})
                    except (tarfile.TarError,OSError,EOFError) as exc:
                        nested.append({'parent':member.name,'sample_error':f'{type(exc).__name__}: {exc}'})
            entries.append(row)
    result={'status':'FORMAT_INVENTORY_ONLY_NO_GEOMETRY_NO_BENCHMARK',
       'source_file':path.name,'source_md5_verified':digest,
       'top_level_entries':len(entries),'top_level_regular_files':sum(x['regular_file'] for x in entries),
       'extension_counts':dict(sorted(types.items())),
       'magic_counts':dict(sorted(magics.items())),
       'first_30_entries':entries[:30],
       'sample_nested_contents':nested,
       'readme_previews':readmes,
       'note':'Samples of nested members are NOT exhaustive; no atomistic structure admitted or source benchmark created.'}
    (out/'FORMAT_INVENTORY.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'TOP_LEVEL_ENTRIES.json').write_text(json.dumps(entries,indent=2)+'\n')
    print('FORMAT_PROBE_PASS top-level entries:',len(entries),flush=True)
    print('EXTENSIONS',json.dumps(result['extension_counts'],sort_keys=True),flush=True)
    print('MAGIC',json.dumps(result['magic_counts'],sort_keys=True),flush=True)
    print('NESTED_SAMPLES',json.dumps(nested,indent=2)[:8000],flush=True)
    print('FORMAT_INVENTORY_ONLY_NO_BENCHMARK',flush=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tar',required=True)
    parser.add_argument('--out',default='outputs/oc20_format_inventory')
    args=parser.parse_args()
    inspect(args.tar,args.out)
if __name__=='__main__':main()
