# Current vs Future Boundary — S-FND-03

Açık bir şekilde S-FND-03'ün ŞU AN (v1) sınırlarını ve GELECEKTE (S-FND-04+) nelerin alınacağını belirtir. SESSİZCE future almak YASAKTIR.

## Current (S-FND-03 v1 IMPLEMENTS HEP — 10 NEW file, 0 modify)
1. 3 Markers: contract / replay / failure_injection. pytest.ini NEW kayıt.
2. F1' PRIME network import static scan (requests/httpx/aiohttp/websocket 4 external library). app/ingest/adapters allowlist.
3. F2' PRIME credential KEY NAME string scan 8 mandatory (api_key/secret/password/token/credential/private_key/BINANCE_API_KEY/OKX_KEY). False positive concat-split pattern koruması, fixture allowlist.
4. F3' PRIME short direction + leverage>1 scan; sadece domain klasörleri app/contracts/app/risk/app/simulation/app/strategies; test/config SKIP.
5. F4' PRIME gerçek emir function isim scan: "send_real_order", "place_order_on_exchange" vs; app production path BLOCKER, test path MINOR.
6. PatternScanFinding / PRGateScanReport typed contract; deterministic hash.
7. Sahplik ayrımı invariant + audit evidence testler (A-1..A-4).
8. Determinism 6 group × 10x.
9. Fail-closed 8 FC.
10. Hard-red 8 HRC.

## Future (S-FND-04+ / Gelecek — S-FND-03 YAPMAZ)
| Future Madde | Hangi Story / Ne Zaman | Şu an Neden Yok | Açık Karar/Gap No |
|---|---|---|---|
| 4. Marker `performance` / `data_quality` / `smoke` / `slow` ekleme | OD-01 sonrası SPEC update + yeni minor hikaye | 3 marker M-4 kuralı, 4. marker fail olur. | OD-01 açık. |
| CI pipeline Github Actions, GitLab CI, `-m contract not replay` PR gate otomasyon | OD-02 sonrası CI infra story. | Non-goals P-03. | OD-02 açık. |
| PYTEST plugin auto-load 3rd party sandbox (disable) | OD-03 kapanınca. | Şu an default dokunulmaz. | OD-03 açık. |
| Unified shared redaction/regex library with S-FND-02 (Foundation core lib — shared between SFND02 masking, SFND03 F2' scan, future SEC credential vault). | S-FND-04 Foundation Core Shared Library (future, PLANNED NOT YET SPEC'D). | G-3 gap açık tutuldu. Şu an iki ayrı regex minimal duplicate. | G-3 açık. |
| F5' prime registry mutation AST scan (AD-23 enforcement additional). | Governance future story. | Şu an HR-4 import 0 bakıyor, fine-grained AST scan YOK. | Future plan. |
| F6' champion bypass scan. | Governance future. | Non-goals P-01. |  |
| Dashboard UI visualization of PRGateScanReport trends. | Dashboard story (far). | G-6. | G-6 açık. |
| Scan report retention, archive, audit rotation chain. | Audit future story. | G-7/G-8. | G-7/G-8 açık. |
| Vault / Secrets Manager integration. | SEC future story. | G-1 açık. | G-1. |
| Registry immutable hash chain + audit log. | Governance future. | G-2 açık. | G-2. |
