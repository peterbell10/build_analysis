from build_analysis.commit_tracker import build_commit_db

db = build_commit_db('/home/peter/git/pytorch', 'upstream/master')
with open('/home/peter/git/pytorch/tools/commit_db.json', 'w') as f:
    db.save(f)
