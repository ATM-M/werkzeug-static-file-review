# Static-file deployment boundaries in Werkzeug

## Summary

This review examines `SharedDataMiddleware` and its use of `safe_join` at Werkzeug commit `f7e37f0bf510fa355fdac3e922cc2078916b021f` (`3.2.0.dev`). It combines source inspection with 32 reproducible project tests and 21 selected upstream tests. All passed on Linux / WSL 2.

The tested configuration serves synthetic backups and dotfiles stored in its exported directory, as well as files reachable through deliberately created symlinks. Tested traversal inputs fail to retrieve outside content. Switching to a clean asset directory prevents the tested sensitive paths from being served while preserving the homepage and CSS asset.

This is a review of deployment behavior, not a claim of a new framework vulnerability. Symlink behavior is explicitly within the trust boundary documented by upstream.

## Source references and threat model

- [SharedDataMiddleware source](https://github.com/pallets/werkzeug/blob/f7e37f0bf510fa355fdac3e922cc2078916b021f/src/werkzeug/middleware/shared_data.py): lines 31 onward describe development-time use; lines 130–138 implement filename filtering; lines 191–209 resolve directory paths and return a basename; lines 233–236 filter and open the file.
- [safe_join source](https://github.com/pallets/werkzeug/blob/f7e37f0bf510fa355fdac3e922cc2078916b021f/src/werkzeug/security.py): lines 153–156 explicitly exclude symlink and filesystem-property validation; lines 195–213 normalize paths and reject unsafe names.

The deployment operator controls the exported directory. Test requests contain no credentials; the fallback application returns a homepage at `/` and 404 elsewhere. The synthetic fixtures deliberately include misplaced files and links. No ability for a remote requester to create or modify those files is established.

The middleware is documented for development use. Production configurations should be evaluated at the actual HTTP server and proxy layer.

## Fixtures

Each case receives a fresh temporary tree:

```text
temporary-root/
  public/
    site.css
    backup.sql
    backup.SQL
    .env
    nested/backup.sql
    linked.txt -> ../private/outside.txt
    linked-dir -> ../private/
  private/
    outside.txt
    archive.sql
  clean-public/
    site.css
```

The baseline mapping exports `public` at `/static`. All contents are synthetic. Successful reads check exact expected response bytes, not just status codes.

## Observations

| Case | Observed result | Interpretation |
| --- | --- | --- |
| Ordinary CSS asset | 200 with expected content | Positive control |
| Missing file | 404 from fallback application | Negative control |
| SQL backup and nested backup | 200 with synthetic SQL content | Files mistakenly included in the export are reachable |
| `.env` | 200 with synthetic configuration content | Dotfiles are not automatically excluded |
| File symlink | 200 with content from `private/outside.txt` | Name validation is not a symlink sandbox |
| Directory symlink | 200 with content from `private/archive.sql` | Linked directories can expose outside files |
| Eight boundary inputs | 404 for plain/encoded traversal, double encoding, backslash, absolute-style suffix, and prefix confusion cases | No outside-file retrieval demonstrated for these inputs |
| HEAD on backup | 200, empty body, expected content length | Reachability metadata; GET establishes content exposure |
| `disallow="*.sql"` | Blocks lowercase SQL and nested lowercase SQL; uppercase `.SQL` and `.env` remain accessible on Linux | An extension deny rule is not a comprehensive content policy |
| `disallow="nested/*"` | Does not block the nested backup | The filter receives a basename, not the relative path |
| Move backup to private directory | Original path becomes 404; CSS and homepage remain 200 | Removes the original exposure path |
| Move backup but retain directory symlink | New linked path still returns backup content | Moving a file alone may leave another public route |
| Export clean asset directory | Seven sensitive paths return 404; CSS and homepage remain 200 | Tested clean deployment meets the intended boundary |

## Remediation

Build the public directory from explicitly selected assets. Keep backups and private configuration outside all public mappings and symlink targets. Review deployment artifacts and ensure untrusted users cannot alter exported content or link targets. Extension filters and disabled directory listings do not replace this boundary.

The tested remediation uses a clean directory containing only an ordinary CSS file. It is a static configuration check, not a general-purpose filesystem sandbox and not a defense against concurrent link replacement or an adversary with local write access.

Impact depends on actual deployed content, process permissions, and other routes to the same files. No CVSS score is assigned to this synthetic setup.

## Verification and limits

- Project tests: **32 passed**.
- Selected upstream tests: **21 passed**, from `tests/test_security.py` and `tests/middleware/test_shared_data.py`.
- Execution metadata, UTC time, file hashes, and JUnit records are included in `evidence/`.
- The upstream tests run without the shared upstream conftest. Their required built-in fixtures are available; this is not a full upstream validation.
- Results cover one development revision on Linux / WSL 2. Native Windows filesystem semantics, special devices, ADS, actual HTTP servers, proxy decoding, package resource loading, and races were not assessed.
- Hashes support artifact comparison, not independent attestation or trusted timestamping.
- No new CVE, upstream-confirmed finding, or accepted bounty is claimed.
