# NEXUS QuoteCheck AI — Ghid rapid pentru Windows (v0.1.0)

Aplicația este **în limba engleză**. Acest ghid este în română, ca să o instalezi ușor.

## 1. Descarcă și extrage ZIP-ul

Deschide **Downloads**, click dreapta pe `NEXUS_QuoteCheck_AI_v0.1.0_Windows_Source.zip` și alege **Extract All → Extract**. Intră în folderul `NEXUS_QuoteCheck_AI_v0.1.0`, acolo unde vezi `setup.bat`, `run.bat` și `app.py`.

## 2. Instalează bibliotecile

Dă dublu-click pe **`setup.bat`**. Va verifica Python 3.12 și va instala componentele pentru citirea Excel și PDF. Este necesar internetul la instalare. Dacă apare o eroare, trimite captura cu fereastra CMD — nu șterge proiectul.

## 3. Pornește aplicația

Dublu-click pe **`run.bat`**. Ar trebui să apară o fereastră neagră și mov intitulată **NEXUS QuoteCheck AI**.

Dacă ai deja Ollama, verifică în CMD:

```bat
ollama list
```

Model recomandat: `qwen2.5:3b` (nu este obligatoriu pentru demo). Dacă lipsește:

```bat
ollama pull qwen2.5:3b
```

În aplicație, selectează modelul și apasă **Refresh Models**. Ollama trebuie să fie pornit pe PC.

## 4. Primul test — fără documente proprii

1. Apasă **Load Demo**.
2. În stânga vei vedea **Supplier_Alpha**, **Supplier_Beta** și **Supplier_Gamma**. Acestea sunt oferte inventate, incluse special pentru test.
3. Selectează **Supplier_Alpha**. Uită-te la cele patru rânduri. Deschide și `samples/Supplier_Alpha.xlsx`, ca să verifici valorile, apoi apasă **Approve All** și confirmă.
4. Selectează **Supplier_Beta**. Verifică documentul `samples/Supplier_Beta.xlsx`, apoi apasă **Approve All**.
5. Selectează **Supplier_Gamma**. Verifică `samples/Supplier_Gamma.pdf`, apoi apasă **Approve All** (are doar trei produse).
6. Apasă **Auto-Map Exact Names** — leagă automat produsele cu denumire identică și aceeași unitate.
7. Deschide fila **Compare Offers & Export**.
8. La **Reference basket**, lasă sau selectează **Supplier_Alpha**. Apasă **Compare Verified Quotes**.

**Rezultat așteptat** (RON fără TVA):

| Ofertă fictivă | Total comparabil | Stare |
|---|---:|---|
| Supplier_Alpha | 934,00 RON | Complete |
| Supplier_Beta | 908,00 RON | Complete — cel mai mic total verificat |
| Supplier_Gamma | Nu se calculează | Incomplete — lipsește Junction box IP65 |

Deși Gamma are prețuri mai mici la trei produse, **nu trebuie să fie declarată cea mai ieftină**, fiindcă nu a inclus tot necesarul.

## 5. Exportă primul raport

Din fila **Compare Offers & Export**, apasă **Export Excel**, **Export CSV** sau **Export HTML**. Alege unde salvezi fișierul. HTML se poate deschide în browser și se poate imprima.

## 6. Testează AI-ul local cu un PDF adevărat

1. Apasă **Import PDF / Excel** și selectează o ofertă cu text selectabil.
2. Selectează oferta importată din stânga.
3. Apasă **Extract with Ollama**. Modelul propune descrieri, cantități și prețuri. Poate dura, mai ales pe CPU.
4. Dă dublu-click pe rânduri și verifică **cu PDF-ul original** că prețurile, cantitățile și unitățile sunt corecte.
5. Apasă **Approve Selected** sau **Approve All** doar după verificare.
6. Pentru același produs cu o altă denumire, dă dublu-click pe rândul ofertei alternative și alege produsul de referință din selector.
7. Pentru sugestii automate de corespondență, poți încerca **AI Suggest Mappings**, dar trebuie să confirmi manual fiecare alegere.

**Important:** AI-ul poate greși. Nu lăsa aplicația să decidă singură achiziții sau sume plătite.

## 7. Cum creezi versiunea .exe

După ce testezi varianta Python, în folderul principal dă dublu-click pe **`build.bat`**. Dacă procesul reușește, vei găsi `dist\NEXUS_QuoteCheck_AI.exe`.

Acest executabil **trebuie testat pe Windows** înainte de publicarea pe GitHub. Chiar și cu `.exe`, funcțiile AI au nevoie de Ollama și de modelul local instalat separat.

## 8. Ce NU face încă versiunea 0.1.0

- Nu citește automat PDF-uri scanate (OCR nu este inclus).
- Nu aplică cursuri valutare și nu compară direct EUR cu RON.
- Nu ghicește TVA-ul, transportul sau reducerile.
- Nu garantează că două produse similare tehnic sunt identice.
- Nu garantează că un furnizor este cel mai bun comercial; compară doar materiale validate.
- Nu modifică niciodată PDF-ul sau Excel-ul original.

**Ghid rapid pentru erori:**

- `No module named openpyxl` sau `pymupdf` → rulează din nou `setup.bat`.
- `Could not reach Ollama` → verifică `ollama list` și că Ollama rulează în Windows.
- `PDF contains no extractable text` → PDF-ul este probabil scanat; momentan nu avem OCR.
- `Approve and correct ALL reference items` → deschide fila Review, corectează elementele cu probleme, apoi aprobă-le.
- `NOT RANKED` → verifică ce produse lipsesc, unități diferite, TVA sau monede incompatibile.

Toate fișierele de exemplu sunt fictive. Nu încărca proiectele care conțin oferte reale pe un GitHub public.
