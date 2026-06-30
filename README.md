# commit-cannon

Experiment to push a single branch past **100,000,000 commits** on GitHub,
beating the current known record (rvfet/committed, ~100K commits/min).

## How it works

`git commit` in a loop tops out at a few hundred commits/sec because it
forks a process per commit. Instead we use **`git fast-import`**, which
streams commit objects directly into a packfile. `generate.py` emits the
stream, fast-import ingests it, and we push **once** at the end so the
network is never the bottleneck.

All commits point at the same empty tree, so disk stays tiny and the only
real cost is object headers.

## Run

```bash
git clone https://github.com/abdulbasit742/commit-cannon
cd commit-cannon
chmod +x run.sh
./run.sh 1000000        # one million commits this batch
```

Run it in batches (each batch chains onto the last via `from`) and keep
going until `git rev-list --count master` clears 100M.

## Speed tips

- Run on your Linux box, fast NVMe disk = fast packfile writes.
- `flush_every` in generate.py controls stream buffering; raise it on big RAM.
- Bottleneck is `git repack` at the end, not generation. Repack once per
  big batch, not per million.
- This is pure I/O, no GPU needed.

## Warning

GitHub Support has deleted record-attempt repos before (csm10495's 22M repo
was nuked). A clone also becomes painfully slow past a few million commits.
This is a stunt repo, do not put anything real here.
