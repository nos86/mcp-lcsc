# LCSC endpoint discovery notes

## Metodo usato
- Tentativo di accesso diretto a `https://www.lcsc.com` durante la sessione cloud agent.
- Risultato: risoluzione DNS bloccata nell'ambiente (`No address associated with hostname`), quindi non è stato possibile ispezionare in tempo reale le richieste di rete dal browser.

## Endpoint JSON assunti (da validare appena disponibile rete)

### 1) Ricerca componenti
- URL: `https://wmsc.lcsc.com/ftps/wm/search/global`
- Metodo: `GET`
- Parametri usati:
  - `keyword` (string)
  - `pageNum` (int)
  - `pageSize` (int)
  - `inStockOnly` (0/1)
  - `basicOnly` (0/1)
- Esempio forma risposta (ridotta):
```json
{
  "result": {
    "productSearchResultVO": [
      {
        "productCode": "C2040",
        "productModel": "NE555",
        "brandNameEn": "Texas Instruments",
        "productDescEn": "Timer",
        "encapStandard": "SOIC-8",
        "stockNumber": 15230,
        "priceList": [{"startNumber": 1, "productPrice": 0.12, "currency": "USD"}]
      }
    ]
  }
}
```

### 2) Dettaglio componente
- URL: `https://wmsc.lcsc.com/ftps/wm/product/detail`
- Metodo: `GET`
- Parametri usati:
  - `productCode` (es. `C2040`)
- Esempio forma risposta (ridotta):
```json
{
  "result": {
    "productDetail": {
      "productCode": "C2040",
      "productModel": "NE555DR",
      "brandNameEn": "Texas Instruments",
      "productDescEn": "Precision Timers",
      "encapStandard": "SOIC-8",
      "stockNumber": 15230,
      "moq": 1,
      "orderMultiple": 1,
      "datasheetUrl": "https://datasheet.lcsc.com/lcsc/xxxx.pdf",
      "paramVOList": [{"paramNameEn": "Supply Voltage", "paramValueEn": "4.5V~16V"}],
      "productPriceList": [{"startNumber": 1, "productPrice": 0.12, "currency": "USD"}]
    }
  }
}
```

## Ordine fallback previsto
1. Endpoint JSON LCSC (sopra).
2. API EasyEDA (se endpoint LCSC non più disponibili/utilizzabili).
3. Parsing HTML statico pagina componente.
4. Playwright opzionale (`LCSC_MCP_PLAYWRIGHT_FALLBACK=true`) come ultima risorsa.

## Limite corrente
Questa documentazione va verificata con cattura rete reale su `lcsc.com` appena l'ambiente consente accesso DNS/HTTP verso il dominio.
