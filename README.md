# SiteProof

**A reusable GenLayer Intelligent Contract that proves a website belongs to a wallet and is an honest page about the project it claims to be.**

- Contract: [`contracts/site_proof.py`](contracts/site_proof.py)
- Network: GenLayer Studionet
- Deployed address: `0x953C97F360263f3eA65114332e2AcAddDBb02cbF`
- Offline tests: [`tests/test_site_proof.py`](tests/test_site_proof.py) (11 tests)

## The trust problem

Launchpads, marketplaces, airdrop pages and grant programs all link to a project's "official website". Users cannot easily tell:

1. whether that website really belongs to the wallet that registered it, or was copied from someone else,
2. whether the page is about the project at all,
3. whether it impersonates a famous coin, company or brand,
4. whether it turned into a scam page after it was approved.

Today each platform checks this by hand, or not at all. SiteProof turns the check into an on-chain record that any app or contract can read, decided by GenLayer validator consensus on the live page.

## How it works

| Step | Method | What happens |
|---|---|---|
| 1. Register | `register_site(subject, url, description)` | The owner registers a project name, a public https page and a short description. The contract returns a personal **verify line** `siteproof:<id>:<last 8 hex of wallet>`. |
| 2. Prove ownership | (off-chain) | The owner adds the verify line to the page. Only someone who controls the page can do this. |
| 3. Verify | `verify_site(id)` | Every validator opens the live page. No page → `NO_WEBSITE`. Verify line missing → `NO_PROOF` (plain substring check, no model call). Otherwise an LLM labels the page `OK`, `IMPERSONATION`, `MISMATCH` or `SCAM_SIGNS`; validators must agree exactly (`strict_eq`). Only `OK` → **VERIFIED**. |
| 4. Retry | `verify_site(id)` | If the result was `NO_PROOF` or `NO_WEBSITE`, the owner can fix the page and retry (3 retries). |
| 5. Re-check | `recheck_site(id, reason)` | Anyone can ask for a re-check of a VERIFIED site with a short reason, once per address. Validators re-read the page. If it now fails (scam signs, mismatch, verify line removed) → **FLAGGED**. |
| 6. Read | `is_verified(id)`, `get_record(id)`, `find_by_url(url)` | Apps and other contracts read the result. |

Every verify and re-check is stored in an append-only `history` on the record (kind, caller, result, reason).

## Why GenLayer is needed

Whether a page "is an honest page about project X" depends on what the live page says right now. A normal smart contract cannot read the web, and an oracle cannot judge meaning. GenLayer validators read the page independently and only store a result they agree on.

## Consensus and safety design

- **Fixed vocabulary.** Model answers are reduced to `OK / IMPERSONATION / MISMATCH / SCAM_SIGNS`, so `gl.eq_principle.strict_eq` can require exact agreement. Anything else becomes `SCAM_SIGNS` (fail closed).
- **Deterministic ownership proof.** The verify line check happens before any model call; a page without it never reaches the LLM.
- **Prompt-injection guard.** Page text and re-check reasons are fenced as untrusted data. A page that tells the model to approve is classified `SCAM_SIGNS`. A re-check reason is only a hint; the verdict comes from the page.
- **Broken links do not crash.** A 404 or timeout is caught and stored as `NO_WEBSITE`, so the record never gets stuck.
- **Spam limits.** One pending record per owner, 500 records in total, one re-check per address per site, 20 re-checks per site, 3 owner retries.

## Methods

| Method | Type | Description |
|---|---|---|
| `register_site(subject, url, description)` | write | Create a PENDING record and its verify line |
| `verify_site(id)` | write, validators | Verify a pending site, or owner retry after `NO_PROOF` / `NO_WEBSITE` |
| `recheck_site(id, reason)` | write, validators | Re-check a VERIFIED site; can set FLAGGED |
| `cancel_site(id)` | write | Owner cancels a pending record |
| `get_record(id)` | view | Record as JSON (status, reason, history) |
| `get_records()` | view | All records as JSON |
| `is_verified(id)` | view | `true` only for VERIFIED records |
| `get_verify_line(id)` | view | The line the owner must add to the page |
| `find_by_url(url)` | view | Latest record for an exact URL |

## Use it from another contract

```python
site = gl.get_contract_at(Address("<SiteProof address>"))
if not site.view().is_verified(record_id):
    raise Exception("Project website is not verified by SiteProof")
```

## Try it (GenLayer CLI)

```bash
genlayer network set studionet
genlayer deploy --contract contracts/site_proof.py

genlayer write <ADDRESS> register_site --args "MoonBaker" "https://gist.github.com/<you>/<id>" "Meme coin for home bakers who share recipes"
genlayer call  <ADDRESS> get_verify_line --args 0
# add the verify line to your page, then:
genlayer write <ADDRESS> verify_site --args 0
genlayer call  <ADDRESS> get_record --args 0
genlayer write <ADDRESS> recheck_site --args 0 "Checking the page is still about MoonBaker"
```

## Run the offline tests

```bash
python tests/test_site_proof.py
```

The tests use a small stand-in for the GenLayer SDK (`tests/genlayer_stub.py`) to cover: verify line format, input validation, one pending record per owner, broken links → `NO_WEBSITE`, missing proof → `NO_PROOF` without a model call, owner retries and retry limit, all model verdicts plus fail-closed parsing, re-check clear vs flag, the re-check reason fenced as untrusted text, a removed verify line flagging the site, cancel, and lookups.

## Studionet evidence

Deployed at `0x953C97F360263f3eA65114332e2AcAddDBb02cbF` (deploy tx `0xf526297de74df2de0c531f54524e8698f8ba51c7ed4e8e0b4b7ce2dee3fb16c0`). The records below are live on-chain and can be read by anyone with:

```bash
genlayer call 0x953C97F360263f3eA65114332e2AcAddDBb02cbF get_records
```

| Record | Page | What was tested | Stored result |
|---|---|---|---|
| 0 | `https://example.com` | Page without the verify line | `REJECTED`, `NO_PROOF` (no model call) |
| 1 | `https://gist.github.com/gurusankar55/REPLACE` (does not exist) | Broken link, then an owner retry | `REJECTED`, `NO_WEBSITE` twice, `retries: 1` (no stuck record) |
| 2 | [MoonBaker gist](https://gist.github.com/gurusankar55/31bd9be25000b8b66a1666c6d6cf2d29) with `siteproof:2:7d5ecef5` | Honest page with ownership proof, then a community re-check with a reason | `VERIFIED`, `OK`; history: `verify OK`, `recheck OK` with the reason stored |

## Origin

SiteProof is the website-trust check from [MemeGuard](https://github.com/gurusankar55/memeguard) (accepted GenLayer project), extracted into a standalone contract so any launchpad, marketplace or airdrop page can reuse it.

## Limits

- Validators judge what the page says; they cannot verify team identity or off-site activity.
- Only the first 5,000 characters of the page are judged.
- Runs on Studionet; this is a prototype, not a security audit service.
