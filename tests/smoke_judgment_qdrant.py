from pathlib import Path
from tempfile import TemporaryDirectory

from zhiyan_legal.judgment_rag import JudgmentManifest, JudgmentRecord, JudgmentVectorStore, chunk_judgment

with TemporaryDirectory() as tmp:
    root = Path(tmp)
    record = JudgmentRecord(
        jid='TPHM,110,訴,123,20210831,1',
        year='110',
        case_word='訴',
        case_number='123',
        judgment_date='20210831',
        title='損害賠償',
        full_type='text',
        content='主文\n\n本件判決如下。\n\n理由\n\n被告應負損害賠償責任。',
        source_url='https://data.judicial.gov.tw/jdg/api/JDoc',
    )
    chunks = chunk_judgment(record, max_chars=100, overlap=10)
    manifest = JudgmentManifest(str(root / 'manifest.sqlite3'))
    store = JudgmentVectorStore(path=str(root / 'qdrant'), collection='test_judgments', dimension=3)
    assert manifest.upsert_record(record, chunks) is True
    store.upsert(chunks, {record.jid: record}, [[1.0, 0.0, 0.0] for _ in chunks])
    result = store.search([1.0, 0.0, 0.0], top_k=3)
    assert result and result[0]['jid'] == record.jid
    assert store.count() == len(chunks)
    store.delete_judgment(record.jid)
    assert store.count() == 0
    manifest.close()
print('QDRANT_SMOKE_PASS')
