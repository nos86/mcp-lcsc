# Fixture reali (non scritte a mano)

Risposte JSON grezze di `GET https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=<id>`,
catturate il 2026-10-19 da rete residenziale italiana.

- C2040: RP2040 (`productDescEn` null, `split` 1)
- C25804: resistore UNI-ROYAL 0603
- C14663: condensatore YAGEO 100nF 0603
- C7593: NE555DR TI (`split` 5)

Usarle come riferimento per i mapping dei campi: sono la forma reale della risposta,
a differenza di `component_response.json` che e' stata ipotizzata.
