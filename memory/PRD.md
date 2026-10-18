# Atelier Fit — Virtual Try-On App

## Problem Statement (original)
Applicazione che da foto e misure reali possa farti provare e vedere indossati vestiti e scarpe che si vorrebbero comprare online.

## Architecture
- Backend: FastAPI + MongoDB (motor), emergentintegrations (Gemini Nano Banana), Emergent Object Storage, Emergent-managed Google Auth.
- Frontend: React 19 + react-router + Tailwind + Shadcn UI, Playfair Display + Manrope, @phosphor-icons/react.

## User Persona
Fashion-savvy online shoppers who want to visualise clothing/shoes on themselves and get accurate size suggestions before buying.

## Core Requirements (static)
- Google login (Emergent-managed)
- Enter body measurements (height, weight, chest, waist, hips, shoulders, inseam, foot) + gender
- Upload personal photo and garment photo
- Generate AI photorealistic try-on image (Gemini Nano Banana)
- Save fittings to wardrobe gallery
- Size recommendation (letter sizes for tops/bottoms/dresses, EU shoe size)
- Measurement-driven avatar silhouette

## Implemented (2026-02)
- Auth: Emergent Google OAuth + session cookie + /auth/me + /auth/logout
- Profile: measurements CRUD, live Avatar3D (SVG) that scales with measurements, inline size preview
- Studio: dual drag-and-drop upload, category + name, Nano Banana try-on generation
- Wardrobe: list with category filters
- TryOn detail: before/after toggle, size recommendation, delete
- Editorial design (Playfair Display + Manrope, boutique layout, neutral palette)

## Backlog (prioritised)
- P1 Shareable look links (public preview page)
- P1 Paste URL instead of upload for garment (web scrape product image)
- P2 Side-by-side multi-garment comparison
- P2 Export look as PDF / print
- P2 Dark mode toggle
- P2 Public showcase feed (opt-in)

## Testing
- See /app/memory/test_credentials.md for the Mongo-based test session approach.
- First iteration passed 100% (both backend and frontend).

## 2026-06 — Pacchetto FAMILY (DONE, tested iteration_4: 100%)
- Card Family: "Fino a 4 utenti. 4 spazi foto, 4 misure separate. Solo per questo abbonamento." (IT/EN/FR/DE, pricing + paywall)
- Sub-profili salvati in `users` con `owner_id`, `is_family_profile`; endpoint GET/POST /api/family/profiles, PATCH /api/family/profiles/{id} (max 4 incl. titolare)
- Header `X-Profile-Id` (localStorage `atelier_active_profile`) isola misure, peso, foto, armadio, prove, outfit. Viene ignorato se il piano non è FAMILY → i profili restano salvati ma bloccati
- Abbonamento/crediti condivisi tramite `User.account_id`; foto base per profilo: `atelier_base_photo:<profileId>`
- Header FamilySwitcher (components/FamilySwitcher.jsx) visibile solo con FAMILY
## Backlog
- P1: screenshot di riserva per "Aggiungi da URL" nell'armadio; Stripe reale (ora MOCK)
- P2: eliminare un sub-profilo

## 2026-06 — Link corti Amazon nell'armadio (DONE, curl + screenshot)
- POST /api/wardrobe/garments/from-url: segue i redirect di amzn.eu/amzn.to/a.co/amzn.com un passo alla volta fino ad amazon.*, estrae l'ASIN e salva il link pulito https://<host>/dp/ASIN
- Fallback immagine Amazon (hiRes/data-old-hires). Se la lettura fallisce, salva comunque brand=Amazon, nome="Prodotto Amazon", image_path=null, is_placeholder=true + link finale
- UI: riquadro "Foto non disponibile" + "Vedi prodotto"; selezionabile, ma la generazione dell'outfit viene bloccata con un avviso (anche dal backend, 400)

## 2026-06 — Fix deploy Render (ImportError ImageContent)
- Causa: emergentintegrations non è su PyPI pubblico → su Render serve l'indice privato. Inoltre il riferimento a litellm con #sha256 andava in conflitto con quello della libreria
- Fix: requirements.txt riga 1 `--extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/`; litellm URL senza #sha256; backend/.python-version 3.11.11; /app/render.yaml (rootDir backend, uvicorn server:app --port $PORT)
- Verificato: pip install pulito senza configurazione pip, import di ImageContent OK, /api/ risponde 200

## 2026-06 — Pagina Termini e Condizioni (DONE, screenshot)
- Nuova pagina pubblica /termini (pages/Terms.jsx): titolo + box con lucchetto "Tecnologia e Metodo Proprietario My Atelier Fit®" (testo esatto dell'utente), prima del footer
- Link "Termini e Condizioni" nel footer della Landing e dell'AppShell
- Il resto del testo dei termini lo fornirà l'utente più avanti

## 2026-06 — Home slogan + Box privacy (DONE, iteration_5 100%)
- Landing: slogan "Zero stress, solo puro shopping" - by Andrea M. e testo principale (testo esatto dell'utente) grandi e centrati; foto Fit score spostata sotto
- PrivacyBox (#E8F5E9, lucchetto) sopra e sotto l'upload in Studio. Testo VERITIERO scelto dall'utente (l'originale "non le salviamo sui server" era falso → rischio GDPR)
- Per rendere vero il testo: GET /api/files/{path} privato (account + profili family); outfit pubblici solo se shared=True (POST /api/outfits/{id}/share); DELETE /api/files/{path} → is_deleted (404); "Cambia foto" elimina la vecchia foto base

## 2026-06 — Account personale e non cedibile (DONE, unit test + screenshot)
- AccountPersonalBox (verde, persona+lucchetto) sotto il box privacy in fondo alla zona upload di Studio, con la frase sul motivo
- Termini: sezione "Account personale" con la riga richiesta
- Backend _enforce_session_limit dopo POST /api/auth/session: 1 sessione (FAMILY 4); i token vecchi vanno in revoked_sessions → 401 "session_revoked_other_device"
- Frontend: l'interceptor mostra SessionRevokedNotice (modale gentile) → "Ho capito" porta alla home

## 2026-06 — Controlli privacy + Termini (DONE, iteration_6 100%)
- Impostazioni: "Cancella tutte le mie foto" (profilo attivo: foto base + immagini e storico di prove/outfit; restano armadio e misure). Lo storage non ha DELETE → l'oggetto viene sovrascritto vuoto + db.files is_deleted
- Impostazioni: "Dispositivi attivi" (user_agent salvato al login) + "Esci da tutti" (cancella tutte le sessioni, anche quella corrente)
- TermsGate: modale con casella obbligatoria; POST /api/terms/accept salva terms_version/terms_accepted_at + log terms_acceptances; TERMS_VERSION="1.0-2026-06" (cambiandola la modale ricompare)
- /termini: bozza completa dei T&C in 14 sezioni (DA FAR RIVEDERE A UN AVVOCATO) sopra il box del metodo proprietario

## 2026-06 — Griglia outfit multi-brand in Prova taglia (DONE)
- "Il capo" invariato. Nuovo blocco OutfitGrid.jsx in fondo a Studio: 2x2 (Maglia/Top, Pantaloni/Bottom, Giacca, Scarpe), drag&drop/clic jpg/png/webp, da 1 a 4 capi
- POST /api/outfit/generate-from-uploads {person_path, items:[{slot,image_path}]}: strati Scarpe→Pantaloni→Maglia→Giacca, 1 credito, salvato in outfits (source "grid"); prompt condiviso _compose_outfit (stesse regole rigide)
- Dopo il risultato: "Incolla link per salvare in armadio" → POST /api/wardrobe/garments/from-screenshot (screenshot come foto + meta dal link; nome generico se il sito blocca)
- Immagini di test: /app/memory/test_person.jpg, test_garment.jpg

## 2026-06 — Prezzo totale, Riprova un capo, Foto capo manuale (DONE, iteration_8 100%)
- OutfitGrid: dopo il risultato si cambia un solo riquadro → "RIGENERA OUTFIT CON IL CAPO NUOVO" (1 prova); i capi salvati restano legati al loro screenshot
- Sotto l'outfit: Totale outfit (somma dei prezzi dei capi salvati) + link "Acquista"
- Armadio: "Carica screenshot" sui capi segnaposto → PUT /api/wardrobe/garments/{id}/image
- IncludedNote "Incluso nel tuo abbonamento Atelier Fit" accanto ai pulsanti di generazione (Single/Family/mese gratuito). La parola "Crediti" non era presente nell'interfaccia

## 2026-06 — Calcolo Automatico Taglia 98% (DONE, iteration_9 + fix)
- Profilo: tolto il form manuale; AutoMeasure.jsx a 3 step (foto intera, altezza + Donna/Uomo, slider peso 40-150 opzionale) + nota privacy
- MediaPipe Pose (@mediapipe/tasks-vision) gira NEL BROWSER: landmark + maschera → rapporti delle larghezze (lib/pose.js, braccia limitate dalle distanze tra le articolazioni). Il backend body_measure.py: altezza = scala, peso/IMC = profondità + regressione; tabelle standard per 6 brand (Zara, H&M, Mango, Nike, Adidas, Uniqlo)
- "Precisione stimata fino al 98%/85% · stima AI", "±2cm stima AI"
- Cifratura Fernet (DATA_ENCRYPTION_KEY in backend/.env — DEVE esserci anche in produzione; se la chiave si perde, i dati non sono più leggibili): measurements.enc, weight_history.weight_enc, foto del calcolo .bin cifrata e mai restituita. Migrazione all'avvio
- Gli endpoint B2B e il pubblico /api/fitting-accuracy/{id} non espongono più il peso né altri dati personali

## 2026-06 — Home senza metro + logo MY ATELIER (DONE, iteration_10 + fix)
- Box "Calcola taglia" (Dashboard): solo Link + Altezza + Peso + Uomo/Donna → POST /api/profile/quick-estimate (body_measure.estimate_from_height_weight; tiene le misure da foto/metro se altezza, sesso e peso (±5 kg) non cambiano) → /product/analyze
- Armadio: sezione chiusa "Verifica con metro (opzionale)" (TapeCalibration.jsx, PUT con method "tape")
- Logo: public/logo.png (originale), logo-trim.png, logo-white.png (trasparente), favicon.ico/png, apple-touch-icon. Classe .theme-dark (#000) per Landing + header dell'app; le pagine interne restano chiare
- In attesa: versione bianca "estiva" del logo

## 2026-06 — Calcola taglia solo con foto (DONE, iteration_11 100%)
- Box Dashboard: solo Link + "Carica una foto intera" + testo dell'utente + "CALCOLA CON LA MIA FOTO"
- La foto viene analizzata nel browser (MediaPipe) → POST /api/profile/auto-measure. L'altezza salvata fa da scala; se manca compare una sola volta "Quanto sei alto?" (viene salvata). Peso e sesso dal profilo se presenti; senza sesso precisione -10 (media dei modelli uomo/donna, tabelle unisex = uomo). Profilo: forget_weight=true quando si sceglie "Preferisco non indicare il peso"
- /api/profile/quick-estimate resta nel backend ma non è più usato dal box

## 2026-06 — Riordino Prova taglia (DONE, screenshot)
- Ordine: Il capo | La tua foto (invertite) → Provalo → griglia outfit multi-brand → box privacy verde + box account personale (il box privacy in alto è stato tolto)

## 2026-06 — Fallback screenshot della tabella taglie (DONE, iteration_12 100%)
- Se il sito blocca, non trova la tabella o va in errore → compare in automatico il riquadro "Non riusciamo a leggere la tabella da questo link - Carica screenshot tabella taglie" (upload jpg/png/webp; il testo incollato resta come opzione secondaria). Nessun messaggio d'errore per l'utente

## 2026-06 — Tabelle salvate + Foto una volta sola (DONE, iteration_13 100% + fix) + Redeploy
- saved_size_charts {account_id, brand_key, group sopra/sotto/scarpe, host_keys, size_chart, fit_notes, saved_at}: salvate da analyze-screenshot/analyze-text; usate quando il link è bloccato o la pagina è piccola (<3000 caratteri, prima della chiamata LLM) o non ha la tabella. Il gruppo viene da categoria o parole dell'URL. I marketplace (amazon, zalando…) non vengono mai abbinati per host. La chiave del brand è il dominio registrabile
- UI: "Tabella X salvata dal tuo screenshot" + "Usa uno screenshot nuovo"; "Usiamo la tua ultima foto intera (del gg/mm)" + "Cambia foto" (measurements.photo_measured_at)

## 2026-06 — Pagina "lavori in corso" (DONE, iteration_14 100%)
- ComingSoon.jsx: nero, logo grande, "Stiamo arrivando", nessun login. Si vede su tutte le pagine (anche da loggati) tranne /termini, finché non si apre ?atelier=2026 o /atelier → localStorage atelier_owner="1" (protezione leggera, non vera sicurezza)
- Da fare quando si va live: togliere il blocco (una riga in App.js)
- 2026-06: la pagina coming soon usa il design dell'utente (titolo testuale "MY ATELIER" + "MY ATELIER .APP - COMING SOON", niente logo immagine). Redeploy avviato
- 2026-06: gate coming soon: /?atelier=esci cancella atelier_owner e torna a COMING SOON. Redeploy avviato. Dominio myatelierapp.it: il record A è ancora 195.110.124.133 (Register.it) → l'utente deve impostare 162.159.142.117 + 172.66.2.113; il CNAME www è già corretto
- 2026-06: stile coming soon dall'ultimo snippet dell'utente (h1 36px/letter-spacing 10px; p 12px/4px/opacità 0.6). atelier_owner ora vale "true" ("1" accettato ancora). Il controllo resta su pathname, non sull'intero URL: url.includes('/atelier') varrebbe per ogni visitatore di https://atelier.app/
- 2026-06: health check pre-deploy: messo tra virgolette DATA_ENCRYPTION_KEY in backend/.env (stesso valore, iniziava con "-"). Seconda verifica del deployment_agent: PASS. iteration_15: decifratura e round trip 100%

## 2026-06 — Dashboard fondatore + countdown (DONE, iteration_16 100%)
- /admin-atelier-77 (non collegata, fuori dal blocco coming soon): password lato server (bcrypt ADMIN_PASSWORD_HASH in .env), cookie httpOnly admin_token 8h (path /api/admin), blocco dopo 5 errori per IP per 15 min. Stile nero/oro. KPI + PRODOTTI HOT (>=1000 views, 4 categorie, conversione). DATI DIMOSTRATIVI (MOCK, _DEMO_PRODUCTS in server.py)
- Countdown sulla pagina COMING SOON fino al 2026-10-25T00:00+02:00, poi "Ci siamo!". Il sito si apre solo su ordine manuale dell'utente

## 2026-10-18 — Owner-only pre-launch gate
- Removed ?atelier=2026 and /atelier bypasses. Public sees only Coming Soon + countdown + small "Accesso proprietario" Google login link.
- Backend: OWNER_EMAILS env allowlist enforced in /auth/session and every authenticated request (403 prelaunch_owner_only). Owner exempt from 1-device limit (4 devices).
- /admin-atelier-77 still password-protected.
- Backlog: at launch, remove/disable OWNER_EMAILS gate; real Stripe; real admin KPIs.

## 2026-10-18 — Clean hands + contact email
- HANDS_RULE added to single try-on and outfit prompts (+ system messages): hands always tattoo-free, no propagation of neck/body tattoos, negative prompt "tattoos on hands".
- Coming Soon: centered "studio@myatelierapp.it" (mailto) under "Accesso proprietario".

## 2026-10-18 — FREE plan card
- PricingCards: FREE (0€, 5 prove/mese, non-paying, no paywall) → UNA TANTUM → SINGLE (Più scelto); FAMILY kept below. Note "Dopo il primo mese gratis illimitato..." (IT/EN/FR/DE).
