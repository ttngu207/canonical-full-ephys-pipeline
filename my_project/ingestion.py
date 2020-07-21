import re
import uuid

from ephys_loaders import neuropixels
from djephys.utils import dict_to_hash

from my_project.init_ephys import lab, subject, ephys, Session
from my_project.utils import get_ephys_root_data_dir, get_ks_data_dir, extract_clustering_info


def ingest():
    # ========== Insert new "Session" ===========
    data_dir = get_ephys_root_data_dir()

    sessions = []
    for subj_key in subject.Subject.fetch('KEY'):
        subj_dir = data_dir / subj_key['subject']
        if subj_dir.exists():
            try:
                meta_filepath = next(subj_dir.rglob('*.ap.meta'))
            except StopIteration:
                continue

            npx_meta = neuropixels.NeuropixelsMeta(meta_filepath)
            sessions.append({**subj_key, 'session_datetime': npx_meta.recording_time})

    print(f'Inserting {len(sessions)} session(s)')
    Session.insert(sessions, skip_duplicates=True)

    # ========== Insert new "ProbeInsertion" ===========
    probe_insertions = []
    for sess_key in Session.fetch('KEY'):
        subj_dir = data_dir / sess_key['subject']
        if subj_dir.exists():
            for meta_filepath in subj_dir.rglob('*.ap.meta'):
                npx_meta = neuropixels.NeuropixelsMeta(meta_filepath)

                probe = {'probe_type': npx_meta.probe_model, 'probe': npx_meta.probe_SN}
                ephys.Probe.insert1(probe, skip_duplicates=True)

                probe_dir = meta_filepath.parent
                probe_number = re.search('(imec)?\d{1}$', probe_dir.name).group()
                probe_number = int(probe_number.replace('imec', '')) if 'imec' in probe_number else int(probe_number)

                probe_insertions.append({**sess_key, **probe, 'insertion_number': int(probe_number)})

    print(f'Inserting {len(probe_insertions)} probe_insertion(s)')
    ephys.ProbeInsertion.insert(probe_insertions, ignore_extra_fields=True, skip_duplicates=True)

    # ========== Insert new "Clustering" ===========
    ephys.EphysRecording.populate(suppress_errors=True)

    clusterings = []
    for ephys_key in ephys.EphysRecording.fetch('KEY'):
        ks_dir = get_ks_data_dir(ephys_key)
        creation_time, is_curated, is_qc = extract_clustering_info(ks_dir)

        clus_key = {**ephys_key,
                    'clustering_method': 'kilosort',
                    'clustering_time': creation_time,
                    'quality_control': is_qc,
                    'manual_curation': is_curated}

        clus_uuid = uuid.UUID(dict_to_hash(clus_key))

        clusterings.append({**clus_key, 'clustering_instance': clus_uuid})

    print(f'Inserting {len(clusterings)} clustering(s)')
    ephys.Clustering.insert(clusterings, skip_duplicates=True)


if __name__ == '__main__':
    ingest()
