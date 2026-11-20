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

## 2026-10-18 — Real Stripe (test mode, claimable sandbox IT)
- Replaced mock checkout. POST /api/subscription/checkout {option, origin_url} → Stripe Checkout (one-time, managed payments w/ fallback to automatic tax). Prices EUR tax-inclusive via setup_stripe.py lookup keys atelier_extra_once 0.99 / atelier_single_30d 2.99 / atelier_family_30d 4.99.
- GET /api/payments/status/{sid} (poll fallback) + POST /api/stripe/webhook; idempotent _apply_paid_session (atomic applied flag). Single/Family = 30 days (plan_expires_at, extends if renewed, auto-downgrade to FREE on expiry).
- Frontend: PaywallModal redirects to Stripe; /payment/success & /payment/cancel (PaymentResult.jsx) → /dashboard with toast. Pricing texts "30 giorni", "Pagamento unico… IVA inclusa", expiry shown in Piano attuale strip.
- Removed /subscription/confirm mock. Tested iteration_17 (100%).
- Backlog: claim Stripe sandbox (onboarding link) to go live; real admin KPIs from payment_transactions.

## 2026-10-18 — FREE quota enforcement + real Owner Room
- FREE: 5 try-ons/month after 30-day honeymoon (DB monthly_tryon_count). When blocked: /api/upload and /api/tryon/generate → 402; frontend 402 interceptor opens paywall globally; Studio guards uploads. Counter: "Ti restano X prove gratuite".
- /api/admin/stats now real: subscribers, distinct logins today, paying (active plan_expires_at), revenue total/month from paid payment_transactions (amount = Stripe amount_total), purchases per plan, last 10 payments, most analyzed products per category. Demo banner removed.
- Tested iteration_18 (100%).

## 2026-10-18 — Crown Owner Room
- Removed /admin-atelier-77, /api/admin/login|logout and password. Owner (OWNER_EMAILS) sees gold Crown icon top-right → /stanza (real Stripe revenue, subscribers, last payments). Others: no icon, /stanza redirects, API 403.

## 2026-10-18 — Revenue chart
- /api/admin/stats returns daily_revenue (last 30 days, paid payment_transactions). Stanza shows gold bar chart (recharts) with tooltip amount + count.

## 2026-10-18 — Owner room cleanup
- Deleted all 11 fake/test users + their data from preview DB (only owner remains).
- Stats exclude owner accounts (OWNER_EMAILS + their family profiles) everywhere; revenue/payments count only livemode=True Stripe payments (stored at checkout). Shows 0 when empty.

## 2026-10-18 — Comandamento 1: Foto unica "Il Mio Avatar"
- Home: single AvatarBox (tap → AvatarCamera: getUserMedia rear cam default, 5s timer, Frontale/Specchio (mirror flips), silhouette overlay, native capture fallback). MediaPipe in browser → asks height/weight/gender once if missing → POST /api/profile/avatar (encrypted, EXIF stripped JPEG, users.avatar_path) + measurements via _measure_and_save.
- GET/DELETE /api/profile/avatar; delete-all photos clears avatar; get_object decrypts /avatar/ paths; outfits fallback to avatar.
- Removed photo upload from CalcolaTagliaBox, Studio ("La tua foto" → AvatarPanel), Profile (AutoMeasure → MeasureResult). Settings: Cambia foto / Elimina foto. AvatarProvider context (lib/avatar.jsx).
- Privacy text truthful (encrypted, account-only) per user choice. Tested iteration_19 (100%).
- NOTE: owner's measurements were overwritten once by a dev test (fake ratios) — owner must take the avatar photo to recompute.

## 2026-10-18 — Avatar: photo check, Family, 2-month reminder
- pose.js rejects before saving: too_dark (mean luma<55), no_head, no_feet, cut_top, cut_bottom, too_far, no_pose → red PhotoIssue panel + "Riscatta la foto" (nothing saved).
- Family profiles: own avatar & measurements (X-Profile-Id); title "Il Mio Avatar · {name}", greeting uses profile name (GET /profile/avatar returns profile_name).
- RefreshReminder on Home when avatar_at > 60 days. Header: brand/lang selector no longer overlaps nav. Tested iteration_20 (100%).

## 2026-10-18 — In-app onboarding + 60-day reminder (email reminders CANCELLED by user)
- OnboardingGate (after terms): step 1 name → PUT /api/profile/display-name (users.display_name); step 2 Avatar photo (skippable "Lo faccio dopo"). Home h1 "Benvenuto, {Nome}".
- GET /profile/avatar returns reminder_due (last of avatar_at / latest weight > 60 days, not snoozed). UpdateReminderBanner on Home: "Ciao {Nome}, vuoi aggiornare foto/peso per mantenere la precisione al 98%?" — Aggiorna ora (opens camera + always shows height/weight form), Ricorda più tardi (POST /profile/reminder/snooze, 7 days). Old weight banner + avatar refresh panel removed.
- Mobile header no longer overflows. Tested iteration_21 (100%).

## 2026-10-18 — Mirror close-up 2-shot + landing restored
- "Specchio da vicino": 2 guided shots (1/2 Busto testa→metà coscia, 2/2 Gambe vita→piedi), own silhouettes + gold line, 5s timer. pose.js extractTwoPartRatios: registerParts() matches overlapping silhouette width profiles (scale s, offset t, dx) → stitched JPEG avatar + ratios (tested: within 5% of single shot, invisible seam).
- "/" for logged-in users shows the original Landing (slogan, "- by Andrea M.", description) with "Entra nell'app" → /dashboard. Not logged → Coming Soon.
- Onboarding step 1 always asks Nome + altezza + peso (+ sesso) → quick-estimate (+weight_history "Iscrizione") + display-name. AvatarBox re-fetches profile before asking body data.
- Tested iterations 22-25.

## 2026-10-18 — Two avatar modes, stitch preview, voice guide
- AvatarCamera modes: "1 foto intera" (single) / "2 scatti · poco spazio" (double, mirror-flip with rear cam), description "Per chi ha poco spazio davanti allo specchio, circa 1 metro"; front/back via flip button. Home note avatar-modes-note.
- Voice (speechSynthesis it-IT): "Busto" / "Gambe" / "Foto intera" at timer start; legs timer auto-starts after shot 1.
- 2-shot: stitched preview (avatar-stitch-preview) with Conferma / Rifai before saving. Tested iteration_26.

## 2026-10-18 — 2-shot mode simplified (never blocks)
- extractTwoPartRatios never throws: soft yellow warnings (too_dark, cut_top, cut_bottom, no_measure) and always returns a stitched photo (simple stack if no anchor). Saved anyway; without ratios → avatar only + quick-estimate from height/weight.
- Double mode: big manual "SCATTA", Timer 10s (voice Busto/Gambe), no auto legs timer, torch toggle (track torch capability), silhouettes solid with drop-shadow. StitchPreview: thumbnails + "Rifai busto"/"Rifai gambe" (retake one part only) + "Conferma e salva". Single mode keeps strict checks. Tested iteration_27 (retake-state bug fixed after).

## 2026-10-18 — Avatar lens 1x + real proportions
- AvatarCamera openNormalLens(): after getUserMedia, if track label is ultra-wide/dual/triple/tele (EN + IT: tripla/doppia/grandangol) switch to the normal back/front lens by deviceId; force zoom 1x via applyConstraints when supported. Both modes.
- pose.js keepRealProportions(): leg fraction (hips→heels / total) clamped to [0.47, 0.60] with hips anchored → no stretched legs. No-anchor fallback: same scale 1:1, photo-2 waist (gold line 14%) aligned to photo-1 waist, seam at hips.
- quick-estimate accepts force=true (used when 2-shot photo is not measurable). Tested iterations 28-29.

## 2026-10-18 — Minimal landing + automatic launch
- Landing.jsx reduced to: header logo + "Entra" (top-right), hero logo, slogan, "- by Andrea M.", description, footer Termini. Entra → /dashboard if logged, else Google login.
- Automatic launch: backend LAUNCH_AT env ("2026-10-25T00:00:00+02:00") — _prelaunch_blocked() only before it; frontend ComingSoon only when !user && Date.now() < LAUNCH_AT (exported from ComingSoon.jsx). After launch everyone sees Landing and can sign up.

## 2026-10-18 — Stitch polish + loading fix
- 2-shot seam moved to waistband (hipY − 15% torso), 48px feather blend, lower-photo exposure matched to upper (brightness gain 0.6–1.6). Backend set_avatar two_shot=true → TWO_SHOT_CALIB_CM = −2 on chest/waist/hips.
- AuthCallback computes target ("/" when login from Coming Soon → homepage preview) before replaceState; /auth/me 10s timeout; gate-loading shows "MY ATELIER". Tested iteration_30 (100%); exposure match added after.

## 2026-10-18 — Truthful sizes + pricing at bottom
- PHOTO_CALIB_CM = −2 now applied to ALL photo measurements (chest/waist/hips), single and 2-shot.
- Product size recommendation is now deterministic (_apply_true_size): LLM only extracts the chart; size = first chart size whose upper bound ≥ user measurement (+1 cm tolerance) on category dims (top/outerwear chest; bottom waist+hips; dress all), ±1 for fit notes; explanation rewritten with real numbers. Fixes M→XL over-sizing.
- Dashboard: PricingCards moved to the last section (before WeightModal/footer).

## 2026-10-19 — Single full-body only
- 2-shot mode removed from the UI (camera always "single"; two-part code in pose.js/AvatarBox now unused). Texts: telefono a 1,5-2 metri, senza zoom.
- Lens policy changed: allow normal/wide (0.5x-1x); switch away only from tele/zoom/periscope/macro lenses; zoom constraint clamped to ≤1x (no digital zoom).

## 2026-10-19 — Wide framing
- Camera prefers ultra-wide lens (label ultra/0.5/grandangol) on the chosen side, never tele; zoom constraint = zoom.min (0.5x where supported). Preview object-contain (full captured frame, no tight crop). Silhouette 80% height (≈10% margin top/bottom). Pose cut checks: top ≥2%, bottom ≤98% of frame. Texts updated.

## 2026-10-19 — 1x default + 0.5x option, phone level, tape calibration
- AvatarCamera: zoom buttons 1x (default: main lens, zoom 1) / 0.5x (ultra-wide lens or zoom.min) with yellow warning; never tele. Level (deviceorientation beta/gamma, "Dritto"/"Raddrizza"); iOS permission requested on tap in AvatarBox.
- Taratura Metro (Profile, MetroCalibration.jsx): POST/GET /api/profile/tape-calibration {chest_cm, waist_cm} → sets current chest/waist to tape values, stores tape_offset_chest/waist = tape − raw photo estimate; future photo measurements use personal offsets (hips keep −2 generic). Raw estimates stored as photo_raw_chest/waist. Badge "tarata col metro". Tested iteration_31 (100%).

## 2026-06 — Copia Look da Modello + Avatar da galleria (DONE, iteration_32)
- Studio › CopyLook.jsx: carica foto modello → POST /api/copylook/extract (Gemini 3.8 Flash box_2d + ritaglio PIL) → elenco capi con taglia utente → POST /api/copylook/apply (Nano Banana, 1 prova, tryon category "look") → /tryon/{id}; POST /api/copylook/save-garment salva il ritaglio nell'armadio
- AvatarBox: "Scatta ora" / "Carica da galleria"; GalleryWarning.jsx avviso obbligatorio + checkbox; secondo avviso se foto > 30 giorni (EXIF via exifr, fallback lastModified)
## Backlog
- P1 Stripe live keys; P2 etichette TryOnDetail in italiano; P2 ritagli più precisi (segmentazione) e pulizia ritagli non salvati

## 2026-06 — Misure reali (profilo serio) (DONE, iteration_33 + fix)
- /profile: "Dacci le tue misure reali, le salviamo una volta sola!" — MeasuresForm (6 obbligatorie: altezza, torace, vita, fianchi, spalle, lunghezza gamba; facoltative peso, età, sesso) + MeasureGuide (silhouette SVG con metro animato 5s, bottone "Guarda come")
- PUT /api/profile/real-measurements (method "tape", measured_at, brand_sizes). Taglie SOLO da misure reali: recommend_size/product analyze → "Completa le tue misure" se incomplete
- RIMOSSO calcolo misure da foto (pose.js, quick-estimate, auto-measure, tape-calibration, MetroCalibration, TapeCalibration). Avatar = "La foto avatar serve solo per la prova vestiti"
- ReminderPopup globale (AppShell) ogni 60 giorni dall'ultimo aggiornamento misure/peso: "Le tue misure sono cambiate?" Modifica ora / Ricordamelo dopo (7 giorni)
- Onboarding: nome → misure → foto

## 2026-06 — Promemoria misure smart per età (DONE, unit + screenshot)
- _update_interval_days: età < 22 → 90 giorni ("Sei ancora in fase di crescita, controllale"), età ≥ 22 o assente → 180 giorni ("Aggiorna peso e misure"); GET /profile/avatar restituisce reminder_due + reminder_young; bottoni "Aggiorna ora" / "Ricordamelo tra 7 giorni"
- Stessa finestra per accuracy/weight-status (niente più "ogni 2 mesi")
- Titolo misure: "Dacci le tue misure reali, le salviamo noi per te!"; testo Home versione finale
- 2026-06: Popup promemoria nero/oro, testi <22 / ≥22 aggiornati; mostrato max 1 volta ogni 7 giorni (snooze registrato appena appare); users.measures_updated_at salvato a ogni salvataggio misure. Primo avviso galleria riscritto: parla solo della prova vestiti.
- 2026-06: Lunghezza piede (foot_cm 18-35, obbligatoria, "Guarda come" con animazione tallone→punta, nota brand). body_measure.shoe_size per brand (Nike mezze taglie, Adidas terzi, Zara intere, altri standard); brand_sizes include "shoes"; recommend_size shoes usa misure reali
- 2026-06: Dashboard disclaimer accuratezza (bronzo, tra Honeymoon e Fitting Accuracy) — nascosto automaticamente quando misure complete e accuracy = 100
- 2026-06: Stripe passato in LIVE (account acct_1UOM2IC7OX8nXTMU, restricted key). Prodotti live creati via setup_stripe.py; webhook live we_1USXDuC7OX8nXTMUcoyXhNcg → https://myatelierapp.it/api/stripe/webhook. Preview e produzione entrambe LIVE (scelta utente). Redeploy avviato.

## 2026-06 — Assistenza studio@myatelierapp.it (DONE, iteration_34 + fix)
- backend/support.py (router): ticket in-app (/api/support/tickets), polling IMAP pop.securemail.pro:993 read-only/BODY.PEEK (mail restano sul server), risposte SMTP smtp.securemail.pro:465 da studio@ con CC andremo2014@gmail.com + copia in INBOX.Sent; thread via In-Reply-To/References
- AI: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929) + KB 10 FAQ adattata ai percorsi reali; richieste non pertinenti → needs_human senza risposta; max 5 auto-risposte per ticket; auto-reply OFF → bozza AI
- Cron .emergent/crons.yml support-poll ogni 15 min → POST /api/cron/support-poll (Bearer WEBHOOK_CRON_SECRET); prima connessione parte dall'UID attuale (non risponde a mail vecchie)
- Frontend: /assistenza (utente, link footer), /stanza/assistenza (owner: inbox, filtri, toggle auto-risposte, controlla mail ora, bozza AI, risposta manuale, stato)
- Env: SUPPORT_EMAIL, SUPPORT_EMAIL_PASSWORD, SUPPORT_IMAP_HOST/PORT, SUPPORT_SMTP_HOST/PORT, SUPPORT_CC_EMAIL, WEBHOOK_CRON_SECRET (vanno aggiunti anche ai Secrets di produzione)
- 2026-06: Sezione "Assistenza / FAQ" nel menu (nav-support + icona mobile): 10 FAQ in accordion (GET /api/support/faq, unica fonte con la KB dell'AI) + domanda libera con risposta AI. Nessuna mail di prova: solo ascolto in entrata (cron 15 min).
- 2026-06: FAQ "Ti è stata utile?" Sì/No (1 voto per utente per FAQ, support_faq_votes; tabella % utile in /stanza/assistenza, rosso sotto 60%). Badge oro sulla corona 👑 con conversazioni da gestire (needs_human o non lette, non chiuse; refresh 60s) → link diretto all'inbox.
- 2026-06: FIX testa tagliata — backend/head_lock.py su tutte le prove (singola, outfit, Copia Look): margine sicuro in alto (max 50px/6%), per capi lunghi (dress o nome lungo/maxi/abito/cappotto…) tela estesa +20% solo in basso (riempita col colore di sfondo), prompt HEAD_LOCK_RULE, face_lock_mask (YuNet models/face_yunet.onnx: viso+capelli+mento, ellisse sfumata) con testa originale reincollata e riallineata sul viso generato; fallback head_safe_zone top 15%; se l'AI cambia proporzioni si adatta l'altezza (mai taglio verticale). Testato: abito lungo su avatar uomo con testa vicina al bordo → testa intera.
- 2026-06: Lunghezza abito reale — backend/hem.py (Gemini 3.8 Flash classifica mini/sopra_ginocchio/ginocchio/midi/maxi/fino_a_terra dalla foto del capo; bonus lunghezza cm dalla pagina prodotto se leggibile; calcolo orlo su altezza utente, avviso "Valuta un orlo di circa X cm" se <165 cm o tocca terra). GET /api/tryons/{id}/hem e /api/outfits/{id}/hem (classificazione in cache hem_info). HemCard (silhouette + linea oro) in TryOnDetail, OutfitResult, OutfitGrid.
- 2026-06: Riprova gratuita — 1 per prova/Copia Look/outfit entro 24h, motivo (sfondo/viso/capo/altro) aggiunto al prompt, nessun credito consumato, lock anti doppio click; POST /api/tryons/{id}/retry, /api/outfits/{id}/retry; log db.free_retries → sezione "Riprove gratuite" in /stanza (GET /api/admin/free-retries). TryOnDetail tradotto in italiano. Refactor: _render_single, _render_copylook.
- 2026-06: Account per email — onboarding Nome → Email (Google, verificata, conferma + testo "La tua email serve solo per ritrovare il tuo account…") → Foto Avatar → Misure (facoltative). users: email unica (indice unique), created_at, free_month_start/free_month_end (+30gg, backfill all'avvio, honeymoon basato su free_month_end), avatar_at (= ultimo aggiornamento avatar), email_confirmed_at, stripe_customer_id (un cliente Stripe per email, riusato al checkout). Blocco doppio abbonamento (409 se piano uguale/superiore attivo >3gg). RefreshBanner 60 giorni (foto avatar o peso) con snooze 7gg, separato dal popup misure 90/180. Privacy nei Termini (§12). DB resta MongoDB (non Supabase/Firebase).
- 2026-06: Ricevuta di pagamento — backend/receipt.py (email HTML nero/oro + testo) inviata da studio@ via SMTP dopo ogni acquisto (extra/single/family) da _apply_paid_session, una sola volta per pagamento (receipt_status su payment_transactions: sending/sent/failed/no_email), copia in INBOX.Sent. Contiene acquisto, importo, data, scadenza, riferimento.
- 2026-06: Brand → l'AI marca brand=true (brand/negozi/agenzie/influencer che propongono collaborazioni). Risposta automatica fissa BRAND_REPLY ("Ciao! Grazie per averci contattato come brand 🙏 …"), ticket nello stato/cartella "brand" (BRAND DA CONTATTARE in /stanza/assistenza, conta nel pallino della corona), email ad Andrea (SUPPORT_CC_EMAIL) "Un brand ti ha scritto - rispondi tu personalmente" con Reply-To del brand; i messaggi successivi del brand non ricevono risposte AI ma rinotificano Andrea.
- 2026-06: WhatsApp Business (Meta Cloud API) — backend/whatsapp.py + support.py: GET/POST /api/whatsapp/webhook (verify token, firma X-Hub-Signature-256, dedup wamid), ticket channel "whatsapp" (phone), stessa KB/AI Claude della mail con risposte brevi; domanda fuori dalle 10 FAQ → "Ti passo subito il titolare Andrea, resta qui che ti contatta a breve" + notifica WhatsApp a +393522260286 (WHATSAPP_OWNER_NUMBER; fuori finestra 24h serve template WHATSAPP_NOTIFY_TEMPLATE) + email; brand anche su WhatsApp. Pannello: sorgente WhatsApp, 📞 CHIAMATA, link Chiama/WhatsApp, risposta manuale via WhatsApp, stato collegamento. IN ATTESA delle chiavi Meta: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_SECRET.

## 2026-06 — Fix OOM produzione (512Mi) su try-on/outfit (DONE, test reale 12MP)
- head_lock.downscale(): JPEG draft decode + thumbnail; persona max 1536px, capi/foto modello max 1024px (alpha PNG preservato)
- prepare: maschera uint8; finalize: risultato ridimensionato alla tela ridotta, blend con cv2.blendLinear (niente copie float32 RGB), del + gc.collect
- Applicato a upload person, _read_photo, _render_single, _compose_outfit, _render_copylook, copylook extract, retry (riusano gli stessi render)
- Foto già salvate: ridotte al volo, originali intatti (scelta utente)
- Misure: prepare+finalize 12MP da ~830MB a ~50MB; worker preview picco ~357MB try-on/outfit, ~410MB copylook extract

## 2026-06 — Outfit in sospeso (ripristino dopo chiusura scheda) (DONE, iteration_35 + 36)
- localStorage `myatelier_pending_outfit`: {avatarPath, selectedItems[{id, image, link, brand}], single{garment_path, category, name, chosen_size}, profileId, timestamp}
- Solo riferimenti (Avatar resta cifrato sul server, capi già caricati); debounce 500ms + flush su cambio app/chiusura
- /studio: modal "Hai un outfit in sospeso, vuoi riprendere?" (Riprendi/Scarta), scadenza 5 min, chiave cancellata dopo generazione riuscita (outfit e prova singola)
- File: lib/pendingOutfit.js, components/PendingOutfitModal.jsx, Studio.jsx, OutfitGrid.jsx. Fix memoria 1536px invariato

## 2026-06 — Size logic: media internazionale + doppia scelta (DONE, iteration_37)
- Fase 1: backend/data/size_standard_media_internazionale.json (uomo/donna S–XXL petto/vita/fianchi + lunghezze t-shirt/felpa/pantaloni/cargo, sneakers piede→EU, pesi per capo, fonti)
- backend/size_fallback.py + POST /api/product/size-fallback: misure metro salvate vs media; taglia = parte del corpo più grande; affidabilità max 93%, al limite 88–90%, mai 98%
- Frontend: components/SizeFallbackDualChoice.jsx (popup "Non ho trovato la tabella di questo brand." con Media internazionale / Screenshot), usato in CalcolaTagliaBox e /analyze; lib/provalo.js (Provalo su di te → /studio)

## 2026-06 — Attesa try-on percepita + tabelle condivise (DONE, iteration_38)
- components/TryOnProgress.jsx: barra nero/beige, rAF easing verso 95% (≈49% a 10s), step testuali 0-20/20-50/50-80/80-95/95-100, nota sotto la barra; 100% "Ecco il risultato!" mostrato ~800ms prima di navigare
- Collegato a: prova singola (Studio), outfit grid, Copia Look, riprova gratuita, OutfitBuilder (armadio)
- Tabelle taglie da screenshot condivise tra tutti i clienti per brand (prima la propria), affidabilità 98% senza chiedere; badge "già letta da uno screenshot di un altro cliente · Affidabilità 98%"

## 2026-06 — Avatar sfocato in attesa + avviso scheda (DONE, screenshot + mock)
- TryOnProgress: Avatar a tutto sfondo, blur 22px→0 e opacità che sale con la percentuale; pannello testi in vetro
- lib/tabNotify.js notifyTabReady(): se la scheda è nascosta, il titolo lampeggia "Il tuo look è pronto · MyAtelier" finché l'utente torna (scelta utente: niente notifiche browser). Chiamato su successo in Studio, OutfitGrid, CopyLook, FreeRetry, OutfitBuilder

## 2026-06 — WhatsApp ufficiale attivo + icona flottante (DONE)
- Chiavi Meta inserite (WHATSAPP_ACCESS_TOKEN system user permanente, WHATSAPP_PHONE_NUMBER_ID 1392661450594917, WHATSAPP_APP_SECRET); numero +39 352 226 0286 "My atelier" verificato via Graph API
- Webhook: https://myatelierapp.it/api/whatsapp/webhook (Verify Token in WHATSAPP_VERIFY_TOKEN); firma HMAC verificata (unsigned → 401)
- FAQ +5: ordini, spedizioni, resi e cambi (gestiti dal brand), appuntamenti atelier, parlare con una persona. Fuori FAQ / operatore → "Per assistenza diretta puoi contattarci al nostro numero aziendale +39 3522260286 anche per chiamate" (tutti i canali, una volta per ticket)
- Rimosso il numero personale: niente più notifiche WhatsApp al titolare (resta l'email di avviso). WHATSAPP_OWNER_NUMBER non più usato
- Frontend: components/WhatsAppButton.jsx verde fisso in basso a destra su tutte le pagine (anche Coming Soon), wa.me/393522260286?text=Ciao My Atelier (REACT_APP_WHATSAPP_NUMBER)

## 2026-06 — Regole identità/mani + anti doppio volto (DONE, test reale + sintetico)
- HANDS_RULE (server.py) ora include IDENTITY STRICT (una sola persona/volto, volto identico, niente face blending/swap, sfondo originale) + mani 5 dita/telefono + negative prompt esteso; usato da prova singola, outfit, Copia Look e retry. Retry "viso" menziona il doppio volto
- head_lock.finalize: se la testa generata non è allineata a quella originale (nessun volto rilevato + phaseCorrelate debole, o centri distanti >35% del volto) NON incolla la testa originale; se dopo l'incolla risultano 2 volti grandi → usa l'output del modello. Log "head_lock: ..."
- Possibile next: hand-lock (incollare mani originali) se le mani restano imperfette

## 2026-06 — Blocco mani originali + "Mani o volto strani" (DONE, test reale)
- server._hand_boxes: Gemini 3.8 flash rileva le mani una volta per foto persona (cache db.hand_boxes) → head_lock.prepare(hands=...)
- head_lock._paste_hand: template match con contesto (NCC ≥ 0.5, finestra ±50%) + controllo cucitura (seam ≤ 28) → incolla la mano originale con ellisse sfumata; altrimenti tiene la mano generata. Coordinate trasformate con la stessa M dell'allineamento testa
- Retry reason "mani_viso" (RetryIn + RETRY_REASONS), stessa riprova gratuita (1 per prova, 24h). FreeRetry: pulsante diretto "Mani o volto strani" (report-hands-face-btn) sotto ogni risultato (TryOnDetail, OutfitGrid, OutfitBuilder); label in AdminAtelier

## 2026-06 — Copia Look: "Salva link outfit modello" (DONE, iteration_39)
- CopyLook ModelLinks: un campo link per ogni capo isolato (riusa SaveLinkRow/OutfitTotal esportati da OutfitGrid con prefix "copylook"), totale "Totale look modello" ("—" se nessun prezzo)
- from-screenshot accetta slot "dress" e name opzionale (nome del capo isolato se il sito non dà metadati)
- Nota: "Salva nell'armadio" della card e il link possono creare due voci dello stesso capo

## 2026-06 — Look completi nell'armadio (DONE, curl + screenshot)
- db.model_looks {id, user_id, model_path, garment_ids[], created_at, updated_at}: creato/aggiornato in automatico quando si salva un link capo in Copia Look (from-screenshot con model_path)
- GET /api/wardrobe/looks (capi risolti, total/priced_count/currency, capi eliminati esclusi), DELETE /api/wardrobe/looks/{id} (solo raggruppamento, i capi restano)
- Frontend: components/ModelLooks.jsx in /wardrobe ("Look completi": foto modello, capi con link acquisto, totale o "—", Rimuovi look); link "Vedi il look completo nell'armadio" in Copia Look

## 2026-06 — Fix "Salva link outfit modello": 1 link per look + gclid + Zalando (DONE, iteration_40)
- CopyLook ModelLinks: un solo campo link → POST /api/wardrobe/looks/from-link {model_path, url, items[]}: look "Totale Look Modello" (brand, title, price, url) + capi isolati con lo stesso link; ri-salvataggio sostituisce i capi precedenti
- _clean_url: decodifica &amp;, sblocca redirect googleadservices/google/doubleclick (adurl/url/q), rimuove gclid/gclsrc/gad_*/gbraid/wbraid/utm_*/fbclid/msclkid/wmc/opc/mpp/otid… e valori Cj0KCQ; usato in analyze, from-url, from-screenshot, looks/from-link
- _fetch_page: fallback curl_cffi (impersonate chrome) per Zalando/Akamai (403 → 200); _structured_meta (JSON-LD, meta price, trackingCurrentAmount) prima dell'LLM → Zalando OppoSuits 89,95 €
- Prezzo a mano se il sito blocca: PUT /api/wardrobe/looks/{id}/price (LookPrice in CopyLook e armadio)

## 2026-10 — Stripe webhook + solo LIVE (CODE DONE, prod pending user)
- Causa webhook 400: STRIPE_WEBHOOK_SECRET in produzione ≠ signing secret endpoint live (we_1USXDuC7OX8nXTMUcoyXhNcg). Utente deve aggiornarlo da Re-publish → Secrets e ripubblicare (chiavi Stripe managed "stripe_sandbox": non modificabili dall'agente; per BYOK l'utente fa Unlink in Manage → Payments)
- Webhook: log firma errata, eventi invoice.paid + customer.subscription.* registrati in db.stripe_events, errori interni → 200, eventi test-mode ignorati; enabled_events aggiornati su Stripe
- Guardia LIVE: STRIPE_LIVE_KEYS (sk_/rk_live_ + pk_live_), altrimenti checkout 503 + log critical. Preview verificata: cs_live_, livemode True
- Verifica prod: creare+far scadere una sessione e controllare pending_webhooks == 0

## 2026-10 — Emergent Payments (Stripe) verso LIVE
- Vecchio collegamento scollegato dall'utente; nuovo collegamento Emergent Payments creato (emergent_sandbox_id 4a865be5…, acct_1UU2OmA3yegZw5Gp, IT), chiavi preview in .env (STRIPE_MODE=test), catalogo ricreato con setup_stripe.py (managed_by emergent)
- In attesa: l'utente clicca il link di collegamento e accede con il suo account Stripe Live → app Emergent Payments installata in live → la piattaforma inietta le chiavi live e ripubblica
- Guardia STRIPE_LIVE_KEYS: con chiavi test il checkout risponde 503 (nessun pagamento con 4242 in produzione). Checkout: managed_payments → automatic_tax → semplice; "No such customer" → usa email

## 2026-10-26 Stripe BYOK Live
- Emergent managed Stripe sandbox DELETED. App uses user's own live keys: STRIPE_LIVE_SECRET_KEY (rk_live), STRIPE_LIVE_PUBLISHABLE_KEY, STRIPE_LIVE_WEBHOOK_SECRET (account acct_1UOM2IC7OX8nXTMU).
- Old STRIPE_* names are platform-managed and overwritten on deploy — never use them again.
- Startup auto-runs setup_stripe.ensure_catalog when live keys present.
- Verified: signed webhook 200, bad signature 400, live checkout session creation OK.
- Backlog: Security Audit (P1), Claude AI models integration (P1).

## 2026-10-26 Qualità foto maniacale + firma + Salva in Galleria (tutte e 3 le modalità)
- backend/tryon_quality.py: Nano Banana Pro (gemini-3-pro-image-preview, fallback 3.1 flash) at 2K with aspect_ratio from canvas; QUALITY_RULES (user positive/negative prompt); QC with gemini-3.8-flash (face_same/hands_ok/garments_ok); up to 2 face/hands-only fix passes that keep ALL garments incl. trousers; best-scoring image kept; flat pad bands trimmed; 'myatelierapp.it' signature burned bottom-right (Playfair Display, backend/fonts); JPEG q94.
- head_lock: lock canvas at 2048 (PERSON_OUT_SIDE), model input still 1536.
- Render jobs: all render endpoints return {job_id}; GET /api/render-jobs/{id} polling (frontend lib/renderJob.js postRender). One running job per user (unique partial index), TTL 1 day, running jobs failed on restart.
- Security: _require_account_paths on /tryon/generate and /outfit/generate.
- Frontend: SaveToGallery button (share sheet on mobile, download on desktop) on TryOnDetail, OutfitBuilder, OutfitGrid. Progress bar TAU 30s with QC step.
- Tested: iteration_41/42.

## 2026-10-26 Home intuitiva + camicia fuori
- Home: riga "Primo mese gratuito · Illimitato" (solo honeymoon, poi TryonCounter) → bottone gigante NUOVA PROVA → Il tuo atelier (max 2 foto grandi) → sezione in fondo "Vuoi anche la taglia perfetta? (Facoltativo)" con MeasuresForm (a tendina) + CalcolaTagliaBox. Prezzi solo nel paywall.
- Eliminati AccuracyBadge, FittingAccuracy (Profile), footer "Metodo Fitting Accuracy", stat cards, Aggiorna peso dalla home.
- Avatar: primo accesso riquadro grande con Conferma foto / Rifai foto; poi AvatarBubble rotondo nell'header (thumb ?thumb=128 su /api/files) → fullscreen "Vuoi cambiare foto?" con note privacy sempre visibili.
- Prompt: _tuck_rule (top senza giacca = sempre fuori dai pantaloni) in tutte e 3 le modalità + controllo QC/fix.
- Tested: iteration_43.

## 2026-10-26 Pagina d'ingresso minimal luxury
- Landing.jsx: fondo nero, "MY ATELIER" (Bodoni Moda), "by Andrea M." (Pinyon Script), bottone ovale ENTRA (login Emergent Google invariato), footer 9px #555 "Termini e Condizioni | Privacy" (/termini, /termini#privacy). Bottone WhatsApp nascosto solo su "/".

## 2026-10-26 Entrata animata + Condividi il look
- index.css .gold-reveal (oro → bianco, 3.2s) / .soft-in su Landing; bottone ENTRA appare dopo ~2.6s.
- ShareLook.jsx (TryOnDetail, OutfitBuilder, OutfitGrid): Web Share con foto firmata + "Provalo anche tu su https://myatelierapp.it"; fallback pulsanti WhatsApp/Facebook/Telegram (solo testo+link) e Instagram (scarica foto + copia invito).

## 2026-10-26 Invita un'Amica + Look condivisi (Stanza)
- Referral: users.referral_code (unique), db.referrals {inviter_id, invitee_id unique, status joined→qualified, paid_at}. Claim POST /api/referral/claim (nuovi <14gg, senza prove). Premi alla PRIMA prova dell'amica (hook in consume_tryon_quota): amica +5 crediti; invitante FREE +5 crediti, pagante +7 giorni. Amica che paga Single/Family (solo livemode): invitante +30 giorni (o SINGLE 30gg). Badge Atelierista TOP a 3 qualificate. Nessun limite.
- Frontend: ReferralClaimer (salva ?ref in localStorage, claim dopo login), InviteFriend card in Home.
- Share events POST /api/share-events (whitelist canali, 1/min per canale); /api/admin/stats daily_shares + referrals; AdminAtelier sezione "LOOK CONDIVISI E INVITI".
- Tested: iteration_44 (+ fix minori).

## 2026-06 — Borsa (bag) accessory
- Added bag slot (5th) to OutfitGrid, AI auto-placement (hand/shoulder/crossbody) via _bag_rule; E2E tested (iteration_46) 100%. Bag slot centred in grid. Redeployed to myatelierapp.it.
- Backlog: lock non-carrying hand when bag present; Security Audit; Claude AI features; refactor server.py.

## 2026-06 — Tuck rule v2 + Studio semplificato
- Suit (auto-detected) -> shirt tucked, tie inside jacket; grid with jacket -> natural; without jacket -> untucked. QC hint for suit.
- /studio: removed Categoria/Nome/Taglia; AI classifies garment (_classify_garment, cached in garment_class).
- head_lock: colour-matched head paste (no halo), hand/phone carved out of head mask (no ghost). Wardrobe labels Italian.
- Tested iteration_47-49 (pass).

## 2026-10-28 — Stripe webhook always 200
- /api/stripe/webhook (FastAPI) returns 200 on every path; invalid signature logged + not processed; invoice.payment_failed recorded. Verified with signed local events. Redeployed.

## 2026-10-28 — Payments ledger, alerts, renewals
- payments_log.py: db.payments (id,email,amount,status,type,reason,createdAt; unique id+status), owner alerts WhatsApp (WHATSAPP_OWNER_NUMBER) + always email copy to first OWNER_EMAILS.
- Webhook: success via _apply_paid_session (once), failures via payment_intent.payment_failed / invoice.payment_failed / async_payment_failed, refunds.
- GET /api/admin/payments (?status=), Admin Room PaymentsLog table (replaced old "ultimi 10" card).
- Cron check-renewals daily 09:00 Europe/Rome -> SINGLE expiring in 2-3 days, email link PUBLIC_APP_URL/rinnova (Renew.jsx -> checkout single), dedupe db.renewal_reminders.
- Tested iteration_50 + tests/test_payments_alerts_renewals.py (10/10).
- Note: Stripe endpoint must also subscribe to payment_intent.payment_failed.

## 2026-10-28 — Foto in Posa + Il Mio Book
- Studio: PersonSource (Usa il mio Avatar / Usa Foto in Posa -> Scatta Foto PoseCamera rear cam + silhouette + 5s timer, Carica da Galleria JPG/PNG). One pose photo shared by Prova Singola + Multibrand; CopyLook keeps avatar.
- After capture ask "Vuoi salvarla nel tuo Book?"; db.pose_book, GET/POST/DELETE /api/book (POST only own kind=person files, not avatar). Header BookButton before AvatarBubble.
- preserve_pose flag on /tryon/generate and /outfit/generate-from-uploads -> POSE_RULE appended to prompt (no extra AI call).
- Header overflow fixed (nav labels only >=1680px, name/email block removed).
- Tested iteration_51.

## 2026-10-28 — FREE_POSE_TRYON
- Kept Gemini engine; POSE_RULE extended (Red Carpet/8k/negatives, clothes not touching hands/face/neck). _hand_info detects phone per hand (cache field phone); in pose mode phone hands not pasted + PHONE_RULE (remove phone, relaxed 5-finger hand).
- QC: phone_present veto, retry once, fail-closed in phone mode; fix prompt never copies phone/clothes from original; missing-garment detection; grid items get AI desc (_garment_info cached).
- head_lock: hand paste similarity gate (no skin patch), scene drift metric -> tight face paste + one SCENE_RULE regen; pad band trim for re-tinted pads. preserve_pose stored on docs and reused on free retry.
- Tested iterations 52-55.

## 2026-10-29 — Doppio Book
- Book (outfit AI only): db.book_outfits_my_atelier, GET/POST/DELETE /api/outfit-book (POST by kind tryon|outfit + ref_id, result_path snapshot). Global BookAsk popup after every try-on end (Studio single, CopyLook via /tryon state fresh, OutfitGrid, OutfitBuilder, FreeRetry). Scarta = not saved, try-on stays in history. Cards: Ripubblica (ShareLook) + Elimina with confirm.
- Le mie Pose = former pose_book: Usa come Avatar (-> /studio pose mode), Ripubblica, Elimina (file kept if used by past try-ons).
- POSE_RULE: fixed identity rules (no beard added, hair/shaved head, glasses), no invented arm/leg tattoos, natural light/no filter; QC hint. delete-all purges both books.
- Tested iteration_56.

## 2026-10-29 — FACE LOCK pose (PREVIEW ONLY, awaiting APPROVA)
- head_lock: _pose_composite (original pixels everywhere, model pixels only where clothes changed; head + zone above chin always original; pads from model), _align_pose (ORB+RANSAC registers model output onto original), face_check credit saver (YuNet, FACE_MIN_CONF 0.75 + brightness/sharpness/size), pose_fail -> regenerate once -> 422 no credit. Fixed dropped elif in finalize.
- /api/pose/check + server guard; SaveBookBar thin bar under result (no modal).
- Foto in Posa hidden for non-owners (Studio PersonSource + Le mie Pose tab). NOT deployed.

## 2026-10-29 — Pantaloni freeze + background jobs (PREVIEW ONLY)
- _hand_info also returns lower (trousers/skirt) and shoes boxes (same cached call). Pose mode: garments not tried on are frozen to original pixels in _pose_composite (top 30% band allows new top hem but never new skin; outerwear -> only no-new-skin); GARMENT_KEEP_RULE in prompt.
- Background renders: postRender stores job in localStorage (atelier_render_job), clears pending draft, hands over to global JobWatcher (AppShell) when user leaves the page; watcher polls /render-jobs/{id}, shows progress pill, on done navigates to /tryon/{id} or shows outfit modal with SaveBookBar. Not deployed.

## 2026-11-01 — Restore after support rollback + surgical owner-only (PREVIEW)
- Support (ticket 297435) restored code to 28 Oct; re-applied all files from commit 2e845cc (Foto in Posa, Books, face lock, background jobs, trousers freeze).
- Owner-only gating: BookButton, JobWatcher, askBook (setBookEnabled), job resume (setJobResume), PersonSource selector (3 radio: Avatar fisso CONSIGLIATO / Galleria / Scatta ora + subtext). Server: _owner_extra adds SURGICAL_RULE (+POSE_RULE) only for owner; surgical => composite on all modes, hands frozen, no-new-skin, ONE generation (no QC/fix/regen) in tryon_quality.render.
- First real surgical avatar test (tryon ebdbaa9e) FAILED visually: model changed body scale -> ghost limbs, hand-box freeze pasted chest skin inside tee, dark replicated border. Awaiting user decision (fix composite vs dedicated fal virtual try-on model). Not deployed.

## 2026-11-01 — Dedicated try-on engine (owner, PREVIEW)
- fashn.py: fal-ai/fashn/tryon/v1.6 via Emergent Universal Key proxy (segmentation_free False, quality, 1 submit, no retry). Owner surgical path in _render_single/_compose_outfit -> _fashn_render (one pass per garment, bottoms->tops->jackets; shoes/bag unsupported -> 422) -> head_lock.surgical_merge (resize/align + _pose_composite with hand-skin lock (top_free -1), no-new-skin, trousers/shoes freeze) -> watermark. Raw engine output saved under tryon_raw/.
- Test 1 (tryon 702a01c8): body/background identical, no ghosts; defect: hand box pasted chest skin into tee -> fixed (hand lock only skin-in-both). Awaiting user approval for next single generation. Not deployed.

## 2026-11-01 — Second surgical test (tryon result 3dd5fbf8)
- Fixes: hand lock = largest eroded skin-in-both blob; phone hand (-2) also locks largest non-skin blob; fashn requests errors -> TryOnError (502); face check before paid submit (head_lock.has_face); raw output path stored in db.tryon_raw; data-URI mime detection.
- Result: chest-skin rectangle gone, bib reduced; phone still partly painted over by tee + small light patch top-right of hand. Awaiting user decision. Not deployed.

## 2026-11-01 — FASHN/fal.ai REMOVED
- fashn.py deleted, no fal.ai calls. Try-on back on Gemini Nano Banana (tryon_quality.render) with head_lock surgical freeze.
- All render jobs (_start_render_job) now OWNER ONLY (403 for others, no credit used).
- 1 test Avatar+black tee OK on face/legs/background; KNOWN BUG: surgical hand freeze box pastes a rectangle of original skin/tattoo over the new shirt (hand+phone area). Fix pending user approval.
- Pending: seated mirror pose test, full outfit top+bottom+shoes.

## 2026-11-01 (2) — Surgical composite fixes (owner only, preview)
- Hand/phone lock now precise (only pixels unchanged between original and model): no chest/tattoo rectangle.
- _pose_composite fills unchanged islands enclosed by new clothes (no skin holes); global no-new-skin freeze removed (pasted background over sleeves); dilate 7.
- SURGICAL_RULE: opaque full coverage + PANTS LOCK + SHOES LOCK.
- Surgical raw model output saved to /tmp/surgical_raw_<tag>.png for free offline re-merge.
- Full outfit (red top+black pants+sneakers) re-merged offline from raw: clean. Seated test needs 1 regeneration to verify new rules.

## 2026-11-01 (3) — STABLE VERSION LOCKED by owner
- Owner approved seated mirror pose (floral shirt, ripped jeans, white Versace, phone hand) in Il Mio Book, outfit f51f09ab (13:16).
- Preset = default for ALL owner pose photos: preserve_pose -> POSE_RULE + SURGICAL_RULE (face/hand/phone/legs/shoes lock) + head_lock precise hand lock + hole fill. No code changes after this point without owner command.
- Stable copies: /app/memory/stable_2026-11-01/{server.py,head_lock.py,tryon_quality.py} (after commit 004e1d2).
- Render jobs remain OWNER ONLY until owner says otherwise. No publish.

## 2026-11-01 (4) — UNIVERSAL POSE LOCK (DWPose local, free)
- pose_lock.py: DWPose ONNX (models/dw-ll_ucoco_384.onnx, onnxruntime CPU). mediapipe rejected (needs libGLES, not in prod).
- tryon_quality.render surgical: skeleton of IMAGE 1 sent as LAST guide image + post-check deviation (max limb joint shift / torso) > 0.30 -> 422, no try-on credit.
- Offline calibration: good results 0.01-0.26, bad (leg lowered) 1.3-2.1, previously "approved" book seated 0.53 (now rejected).
- SURGICAL_RULE: universal pose lock any pose + no added objects (bag only if Borsa slot).
- Owner decides tests (no agent generation). Still OWNER ONLY, not published.

## 2026-11-01 (5) — Pose photos robustness
- Root causes (logs): leg-raised photo -> head_lock alignment failed (aligned=False, face behind phone/aspect change) -> pose_fail; half-body screenshot -> pose deviation 0.72 (feet invented) -> rejected. NO nudity/underwear filter exists.
- head_lock._register: ORB+RANSAC similarity registration of model output onto original (any aspect/zoom) used first for posed photos; _pose_composite works without detected face; POSE_CHANGE_MAX 0.75.
- pose_lock.is_half_body (no ankle in frame) + HALF_BODY_RULE + canvas bottom extension 0.7 + non-pose finalize (head/hands lock) when bottom/shoes requested; pose check upper joints only.
- Not generation-tested (owner tests himself).

## 2026-11-01 (6)
- pose_lock.deviation: Procrustes (similarity fit) before measuring -> zoom/framing no longer counts. Half-body result 14:04 now 0.20 (passes).
- Leg-raised photo: Gemini lowers the leg even with skeleton guide (full dev 0.74) -> stays REJECTED, no credit. Owner accepts (ControlNet = paid, declined).
- DWPose model gitignored (134MB): auto-downloaded from HuggingFace on first use (pose_lock._session).
- hand_boxes/face_checks cache cleared for owner. Owner approved production deploy, owner-only (customers see maintenance).

## 2026-11-01 (7) — MULTI-PASS legs (free, Gemini)
- server._multipass_outfit: full-figure surgical outfits with bottom/shoes -> pass1 uppers via _compose_outfit(raw=True) (legs frozen), pass2 Gemini on DWPose legs crop (LEGS_PASS_RULE + skeleton), _register + _pose_composite (hands locked) + feathered paste, full pose check, watermark.
- Test 14:31: leg raised on bed -> KEPT (dev 0.14) delivered; central -> OK (dev 0.14); half-body -> Gemini changed pose/scene (dev 0.75) rejected, no credit.
- Deployed owner-only.

## 2026-11-01 (8)
- 22:25 failure root cause: owner uploaded a SCREENSHOT of the app as pose photo -> model returned only the embedded photo -> registered scale 0.5, changed 0.91 -> pose_fail. NOT a leg/underwear filter.
- head_lock.crop_screenshot (auto-crop embedded photo) applied in _render_single/_compose_outfit/_multipass.
- ALL surgical rejections removed (pose deviation + pose_fail only logged); multipass legs<4 -> single-pass fallback.
- Test on screenshot photo: delivered, raised leg kept (dev 0.23). Seam ghosting at crop edges minor; slippers on rug removed by legs pass. Preview only (not deployed to My Atelier).

## 2026-11-01 (9) — SLEEVE LOCK
- pose_lock.arm_masks: DWPose shoulder->elbow->85% wrist strip forced to model sleeve; hand kept = hull of finger points (wrist root excluded, cuff covers wrist tattoo).
- head_lock._pose_composite(arms=...) used in surgical posed finalize; multipass legs pass restores pass-1 sleeves/hands (strip & changed-vs-orig) so elbows on knees never repainted.
- Test 22:46 leg-raised screenshot photo (floral/jeans/white shoes): elbow hole closed, full sleeves, raised leg kept (dev 0.17). Preview only.

## 2026-11-01 (10) — /test-pose (owner only)
- pages/TestPose.jsx: shared outfit (top/bottom/shoes upload) + 8 stock pose cards (Unsplash/Pexels), manual TEST per card (1 generation, one at a time), Cambia foto, before/after.
- POST /api/test-pose/import {url}: owner only, unsplash/pexels hosts only, cached per URL in db.test_pose_imports.
- _require_pose_face now non-blocking (log only) per owner request.

## 2026-11-01 (11) — Clean edges + PDF
- multipass legs paste limited to pose_lock.legs_mask (hip->knee->ankle strips + feet hull, feathered + crop-border ramp): background/mirror/floor objects (slippers) stay identical.
- _pose_composite: MORPH_OPEN ellipse 5 on change mask drops thin ghost lines (shifted frame edges).
- Offline sim (no generation): mirror-frame ghost gone, slippers kept.
- /test-pose: ESPORTA PDF PRIMA/DOPO (jspdf 2.5.2, lib/posePdf.js): cover + 1 A4 landscape page per tested pose. PDF not yet exercised with real results (needs owner TEST).

## 2026-11-01 (12)
- posePdf.js agency book: black cover with /logo-trim.png, per pose page black header band with logo + only PRIMA/DOPO images. Verified by exporting a real pair (2 pages OK). No generation.

## 2026-11-01 (13) — Identity/framing fixes
- Crossed legs on bed (23:11) went HALF-BODY path (ankles hidden) -> extension + zoom + legs on floor. is_half_body now requires knees AND ankles missing.
- crop_screenshot trims letterbox bars (flat rows/cols) before screenshot detection.
- Sleeve lock per arm segment (upper/fore): segment kept same as photo -> forearm stays ORIGINAL (no invented tattoos on short sleeves); segment changed -> whole segment new sleeve. Verified offline on floral long-sleeve (no holes) and black tee (original forearm tattoos).
- Not done: light/quality enhancement (would alter original pixels).

## 2026-11-01 (14) — Crossed legs full outfit
- legs_mask: + dilated hull of all lower-body points (score>0.2) for hidden shins/ankles + waist band above hips; multipass crop Y0 extended to 35% torso above hips; LEGS_PASS_RULE crossed-legs draping line.
- Test 23:39 crossed-legs bed (floral 43e5182f + BLACK CRAFT 868517 + white 2d56df): legs fully covered & crossed, shoes on feet, no old waistband, bg identical (dev 0.05). 2 generations used (first 23:37 failed: bare shins + tank hem).

## 2026-11-01 (15) — Clean hand edges
- Ghost bands beside forearms: pass1 bare-forearm segment forced ch=0 on whole strip (incl. shirt beside arm) -> now only pixels skin in both photo and result.
- Pass2 keep: hands = finger hull & skin (eroded, 0.8px feather); bare arms no keep; sleeves inner part only. Legs paste feather fixed 2.5px (sharp hem/pants edge).
- Legs raw saved to /tmp/legs_raw_*.png. Offline pass1 check OK (side ghosts gone). Not verified with a new generation.

## 2026-11-02 (16) — Hands halo
- ROOT CAUSE: _register rejected any model output with a different resolution (scale range on absolute px) -> legs pass fell back to STRETCH resize -> misaligned hands/bed -> halos. Now scale judged relative to plain fit.
- Pass2: no hand box lock; hand keep = finger hull (dilate 0.04 span) & skin & same-as-legs-pass (<40) ; legs mask dilated 0.5 thigh; feet radius 0.45 thigh.
- Offline re-merge (raws in /app/memory/raw) of 23:59 crossed-legs camo result: halo under fingertips gone, shoes complete, bed seam gone; outfit 582858b4 result replaced (free).

## 2026-11-03 (17) — Bottom stripes
- ROOT CAUSE: pose photo was a phone screenshot with Android nav bar (black + small icons) at bottom; letterbox trim missed it (not flat) -> model output did not cover that band -> _register BORDER_REPLICATE smeared last rows = vertical stripes under feet/watermark.
- crop_screenshot: bar rows = flat OR >85% black OR >97% white. _register: pixels not covered by the model output keep the original photo.
- Re-merged (free, raws in /app/memory/raw) outfits 0d6ca71d and b965d3b7: full height 691x1221, feet+sand visible, watermark kept, no stripes; Book entries updated too.
- hand_boxes cache cleared (crop changed). Testing agent NOT run (owner forbade tests).

## 2026-11-03 (18) — Heel cut + bag halo
- multipass: feet >92% of height + shoes -> +8% floor (pass1 canvas extend, orig replicate); uncovered floor inpainted, and if the model drew no floor the image is cut just below the new shoes.
- BAG IN HAND (bag in uppers): no original hand/forearm paste in pass1 (arms hands zero, fore segs dropped) and no hand keep in pass2 -> no ghost hand on bag.
- head_lock arms: hand kept only where result still shows that hand.
- Re-merged 35b100a6 (free): full red heels, clean bag corner, watermark kept (691x1245). No tests per owner.

## 2026-11-12 — POSE SEDUTE: 3 regole permanenti (Posa 6) (DONE, test manuale offline + 3 generazioni)
- Rilevamento automatico posa seduta: `pose_lock.is_seated` (ginocchia < mezzo busto sotto le anche)
- Regola 1 NIENTE ALONI MANI: `head_lock._seated_hands` rimette le mani originali spostate sulla posizione delle mani generate (offset DWPose), silhouette esatta, bordo netto (sigma 0.9)
- Regola 2 NIENTE BUCHI: `head_lock._seated_composite` — gambe, avambracci e spazi tra le dita sempre dal risultato (tessuto continuo); bordo del capo ridecisio pixel per pixel (niente scie)
- Regola 3 NIENTE GAMBE CHE SPUNTANO: `head_lock.seated_cover` copre di grigio la pelle nuda delle gambe nell'immagine inviata al modello + prompt `SEATED_RULE`/`SEATED_GREY_RULE` (server.py); controllo pixel gratuito `tryon_quality._seated_legs_check`: se resta pelle (>30%) UNA sola passata di copertura (`SEATED_FIX_PROMPT` + `seated_cover_merge`), mai di più
- Attivo per prova singola e outfit a passata unica con capo lungo (abito/tuta/pantaloni lunghi, non mini/shorts/gonna); prompt anche nella passata gambe del multipass
- Raw salvati in /tmp/surgical_raw_* e /tmp/seatfix_raw_* per ri-merge offline gratuiti; script in /app/memory/p6/

## 2026-11-12 — REGOLA MADRE: MOSTRA SEMPRE LA FOTO (DONE)
- Eliminati tutti i blocchi sulla foto generata: blocco gambe (LEGS_BLOCKED_MSG, multipass + fallback) e blocco volto/posa (pose_fail 422) → la foto si consegna sempre, i controlli restano solo nei log
- Eliminato il pre-controllo viso nel frontend (PersonSource faceOk): la generazione parte sempre
- Sotto ogni foto generata: "Prova generata - dimmi cosa correggere" (components/ResultNote.jsx: TryOnDetail, OutfitBuilder, OutfitGrid, JobWatcher, TestPose)
- La posa resta intoccabile: nessuna correzione cambia la posa

## 2026-11-12 — MODO DI VESTIRE BLOCCATO (DONE)
- `DRESSING_RULE` (server.py) aggiunta a ogni prompt di prova: singola, outfit, passata gambe, copia look. Top aderente con orlo appoggiato sulla vita alta (né dentro né sopra), pantalone a vita alta che segue la posa, ricami intatti, proporzioni reali, giuntura pulita, posa identica
- `_tuck_rule` UNTUCKED ora = orlo appoggiato sulla cintura (non più "fuori e lungo sui fianchi"); testo del controllo qualità allineato

## 2026-11-12 — REGOLA FISSA MANI/AVAMBRACCI + MAGLIA FUORI (DONE)
- Multipass passata gambe (server.py `_legs_attempt`): rimette SEMPRE sopra i pantaloni nuovi la maglia della passata 1 (silhouette intera, pizzo chiuso; i fori del pizzo mostrano il braccio solo sul braccio, altrove i pantaloni nuovi = niente aloni marroni), le mani esatte (palmo+dita DWPose) e gli avambracci nudi. Prima la passata gambe cancellava mani e maniche
- `_tuck_rule`: maglia FUORI, cade sopra la cintura (sostituisce "appoggiata sulla vita"); `DRESSING_RULE` + regola fissa mani/avambracci mai spariti, zero aloni, uomo/donna/ogni outfit
- Outfit 6223a9a6 corretto con rimontaggio gratuito (pantaloni e scarpe identici). 3 generazioni provate sulla passata gambe: non migliori (pantaloni cambiati), scartate
- Re-run gratuito: /app/memory/p7/rerun.py (sostituisce il modello con i raw salvati)

## 2026-11-12 — Outfit 6223a9a6: maglia della 2a foto + mani della 1a (DONE, 0 generazioni)
- Rimontaggio gratuito: base = risultato originale (maglia vera, pantaloni/scarpe intatti) + mani originali (silhouette DWPose, bordo scuro tolto). Script in /app/memory/p7/
- DRESSING_RULE: + "REAL FABRIC, NEVER CARTOON" e "SLEEVES END AT THE WRIST" (niente strascico)
- 2026-11-12: outfit 6223a9a6 — base = foto senza braccia (maglia non toccata) + 1 generazione di ritocco solo braccia/mani, composta SOLO nella zona avambracci/mani (script /app/memory/p7/arms.py)
- 2026-11-12: foto corretta (outfit 6223a9a6) messa in cima (created_at aggiornato, is_reference=true) e salvata in "Le mie Pose" come foto di riferimento per i prossimi outfit; outfit fc4a4a69 (body nero) scartato. DRESSING_RULE + "NO OLD CLOTHES UNDER THE NEW ONES"

## 2026-11-12 — BASI DEFINITIVE posa seduta (DONE, 0 generazioni)
- Collection `pose_bases`: MA-SEDUTA-A01 "BASE A - MAGLIA COMPLICATA" (da outfit 55ae6eda, UI telefono ritagliata) e MA-SEDUTA-B01 "BASE B - BRACCIA SCOPERTE" (da outfit 23482b0b); file anche in `files` (kind person)
- GET /api/pose-bases; `_auto_base` in prova singola + outfit (griglia e guardaroba): se la foto scelta è una base -> capo con maniche = A, smanicato = B, dubbio = resta quella scelta
- Frontend: components/PoseBases.jsx nel pannello "foto in posa" (Studio) con codici visibili
- 2026-11-12: BASE A + pantalone nero trasparente + zeppe: 1 generazione, sopra i fianchi pixel identico a BASE A (script /app/memory/p8/lower.py), salvato come nuovo outfit in cima
- 2026-11-12: BASE A + pantalone nero OPACO + zeppe: 1 generazione (raw2), busto pixel identico, nuovo outfit in cima
- 2026-11-12: BASE A + pantalone pizzo nero trasparente (prodotto df4efd9e) + zeppe: 1 generazione (raw3), busto pixel identico a BASE A, niente body nero
- 2026-11-12: final4 = final3 + pavimento pulito (pezzi pizzo rossi tolti) + sandali rifatti: 1 generazione (raw4) composta solo su pavimento/piedi
- 2026-11-12: NUOVA BASE A = MA-SEDUTA-A02 (final5: zona nera centrale rifatta in pizzo trasparente, 1 generazione). A01 archiviata in pose_bases_history

## 2026-11-12 — REGOLA ASSOLUTA MY ATELIER (DONE)
- `tryon_quality.REGOLA_FISSA_MY_ATELIER` (testo del proprietario, verbatim) anteposta al system prompt di OGNI chiamata al modello immagini (`_image_call`)
- `old_clothes_qc` (modello testo economico): vestito vecchio visibile? capi fuori dagli slot? doppio strato? (cintura/pannelli dei pantaloni ammessi non contano)
- `_old_clothes_loop` (server.py) su prova singola (`_render_single` -> `_render_single_once`) e outfit (`_compose_outfit` -> `_compose_outfit_once`, anche multipass): se fallisce rigenera max 2 volte (OLD_CLOTHES_MAX_REGEN) col difetto nominato; consegna SEMPRE la migliore, mai blocco

## 2026-11-12 — CAPI TRASPARENTI + SERVER ESTERNO (DONE)
- Upload capo: trasparente=TRUE automatico se PNG con alpha reale o nome con trasparente/tulle/organza/voile/sheer/see-through/velato; nome con pizzo/lace/mesh/rete/chiffon/velo -> chiede "Sembra trasparente, confermi?" (files.transparent / transparent_maybe)
- Checkbox "Questo capo è trasparente / velato / pizzo / tulle": components/TransparentToggle.jsx (Studio capo singolo + ogni slot griglia outfit); GET/POST /api/garments/transparent
- Interruttore USA_SERVER_ESTERNO_TRASPARENZE: db.app_settings {_id: transparent_ext, on, used}, OFF di default; GET/POST /api/admin/transparent-ext (solo proprietario); components/TransparentSwitch.jsx nella griglia outfit. ON = max 2 generazioni esterne, poi OFF da solo
- Esterno: fal.ai fal-ai/image-apps-v2/virtual-try-on via Universal Key (backend/fal_tryon.py). Prova singola: capo trasparente + ON -> esterno. Outfit griglia: capi coperti col flusso normale, poi ogni capo trasparente con l'esterno sul risultato. Se l'esterno fallisce -> foto del flusso normale + avviso "Capo trasparente in elaborazione speciale" (campo notice, mostrato da ResultNote)
- Flusso capi coperti invariato
- 2026-11-13: VISO BLOCCATO ESTERNO (backend/ext_lock.py): sul risultato fal rimette foto originale (viso, capelli, mani, braccia nude per capi sotto, sfondo); dall'esterno solo zona capo; vecchio capo dove l'esterno mostra pavimento -> ricostruito dal pavimento originale (inpaint); luce riallineata sul pavimento comune. Collegato in _ext_tryon. Testato gratis su /app/memory/p8/fal_test.jpg
- 2026-11-14: server esterno trasparenze passato a FAL_KEY del proprietario (BYOK, fal-client SyncClient, backend/fal_tryon.py). Test: chiave riconosciuta ma account fal senza credito (403 Exhausted balance)

## 2026-11-14 — Trasparenza automatica + velocità (DONE)
- Tolte le caselle "trasparente" (TransparentToggle eliminato, endpoint /garments/transparent rimossi). Resta solo l'interruttore SERVER ESTERNO TRASPARENZE
- Rilevamento automatico all'upload del capo, in background (non rallenta): fal.ai `openrouter/router/vision` (google/gemini-2.5-flash) con FAL_KEY; se fal non risponde -> riserva Emergent `tryon_quality.transparent_qc`. Salvato in files.transparent/transparent_by. Calcolato solo se l'interruttore è ON
- Velocità: multipass gambe max 1 correzione (prima 2); ANTEPRIMA SUBITO: render_jobs.preview_path (dopo passata 1 e dopo il primo risultato prima del controllo Regola Fissa), GET /render-jobs ritorna preview_path, frontend components/RenderPreview.jsx (evento PREVIEW_EVENT da lib/renderJob.js)

## 2026-11-15 — LIVE TRY-ON ENGINE (DONE, test offline senza generazioni)
- Niente più basi fisse: `_auto_base` eliminato (si usa sempre la foto LIVE scelta). Endpoint /pose-bases resta solo per scelta manuale
- Trasparenza automatica a 3 livelli (fal vision, riserva Emergent): files.transparency none|light|high. `tryon_quality.coverage_rule`: LIGHT -> fodera nude opaca; HIGH top -> reggiseno stesso colore del capo; pantaloni -> vita/fianchi solidi + fodera opaca sotto il pizzo
- DRESSING_RULE + "LIVE TRY-ON ENGINE — GARMENT BUILD" (parti solide opache, maniche attaccate, pantaloni completi, mai solo trasparenza, posa live, bordi puliti). SURGICAL_RULE: trasparenza solo dove lo screenshot la mostra, sopra fodera
- Sistema (Gemini) costruisce SEMPRE l'outfit intero; in parallelo il server esterno (fal) per ogni capo trasparente. `ext_lock.lace_layer`: dal fal SOLO il pizzo, dentro il capo del sistema, mai su pelle (i fori mostrano la fodera), mai su vita/fianchi/spalle, mani, sfondo, firma. `lock_original` eliminato (causava aloni bianchi e maniche staccate)
- `_old_clothes_loop`: 3 varianti in parallelo, rotte scartate, CONTROLLO FINALE (vestiti vecchi, parti solide, maniche, pantaloni completi, copertura, posa, bordi) -> migliore; se tutte falliscono 1 ricostruzione. Merge pesante in serie (`tryon_quality._HEAVY`) per la memoria
- Nota: costo 3-4 generazioni per prova; in produzione 512Mi il multipass x3 va monitorato

## 2026-11-15 (2) — REGOLA GLOBALE pavimento + foto buona ripristinata (DONE, offline, 0 generazioni)
- Prompt: GLOBAL RULE in DRESSING_RULE (capo solo sul corpo, pavimento pulito, figura intera, niente inset/props, top+pantaloni completi)
- Scelta varianti: prima COMPLETEZZA (outfit_incomplete/pants_incomplete/solid_parts) poi difetti; lo sporco sul pavimento non viene mai contato (si pulisce dopo)
- `_clean_floor` (server) dopo la scelta: crop inset/screenshot (+ firma rifatta), 2 rilevamenti AI debris (`tryon_quality.debris_boxes`) + `ext_lock.clean_floor` (pavimento originale riallineato; dove l'originale aveva il corpo -> inpaint). Nessuna rigenerazione
- `head_lock._crop_white_card`: screenshot galleria (card con angoli arrotondati tra bande bianche) -> solo la foto; cache hand_boxes/face_checks svuotate
- Reggiseno ANNULLATO dall'utente: capi trasparenti sempre su FODERA OPACA (nude o nera), mai reggiseno, mai spalline staccate; il controllo finale lo segnala. Scelta reggiseno / 409 rimossi
- Foto buona = outfit 6a28416d (spalle attaccate, niente reggiseno): solo pavimento pulito -> result 97bf3b72 (originale in result_before_clean). Outfit b8196593 rimesso com'era

## 2026-11-15 (3) — INQUADRATURA 1:1 (regola fissa, tutte le prove) (DONE, offline)
- FRAMING 1:1 nel DRESSING_RULE: mai zoom/crop, piedi e scarpe interi con margine, vestito lungo = frame allargato in basso, corpo/posa/scala/sfondo/luce bloccati, nel dubbio zoom-out
- `_feet_extend`: piedi oltre il 90% dell'altezza -> +10% di tela in basso (singola + outfit; multipass FEET_EDGE/FEET_EXTEND senza vincolo scarpe). head_lock.prepare: bottom = max(extend, pad capo lungo)
- Tolti i tagli: multipass "taglio sotto le scarpe" eliminato; `_trim_pad_bands` non taglia più la banda in basso (diventa pavimento specchiato); `_crop_white_card` non rade più i bordi, gli angoli bianchi vengono ricostruiti (inpaint solo bianco che tocca il bordo)
- Controllo finale: scarpe tagliate / foto zoomata = outfit_incomplete
- Foto buona 6a28416d rifatta senza tagli: scarpe intere -> result 3f40b138

## 2026-11-15 (4) — REGOLA ANTI-ARTEFATTO (DONE, 1 generazione di zona)
- DRESSING_RULE + ANTI-ARTIFACT (mai macchie nere/sfocature/doppioni/dita doppie/piedi deformi/scarpe fuse; piedi e mani nitidi, 1 per lato, 5 dita; zona rifatta in HD, perfetta al 200%)
- Controllo finale: flag local_artifacts (conta come difetto). Se la migliore lo ha: `_fix_artifacts` -> `tryon_quality.artifact_boxes` (AI, max 2 zone) -> `fix_zone` (1 generazione HD su crop quadrato) -> registrato e incollato SOLO sul difetto sfumato. Il look non si rigenera
- Outfit 33ad72ac (sandali neri, foto di riferimento): macchia nera sotto il piede sinistro rifatta (1 generazione) + puntino rosa tolto -> result 2ed1cd5f (originale in result_before_fix)

## 2026-11-15 (5) — REGOLA UNIVERSALE TACCHI (DONE, controllo gratuito verificato)
- DRESSING_RULE + HEELS/SHOES: scarpa+tacco pezzo unico, piedi interi, due scarpe coerenti/speculari, tacco nella direzione della scarpa; vietati tacco staccato/doppio/finto/a terra, piede cancellato
- Controllo finale: flag shoes_wrong (difetto). artifact_boxes cerca anche i difetti di tacchi/scarpe. shoes_wrong o local_artifacts -> `_fix_artifacts` (solo zona piede, 1 generazione HD) con la foto intera come IMAGE 2 di riferimento per il piede giusto

## 2026-11-15 (6) — VELOCITÀ (DONE solo anteprima, nessun render di prova)
- `_old_clothes_loop`: ricostruzione SOLO se nessuna variante è utilizzabile (incomplete); trasparenza/body sotto pizzo non la attiva più
- `_multipass_outfit`: niente correzione gambe (pass 2) se il capo basso è trasparente/pizzo o se fallisce solo il controllo AI; stesso salto nel fallback single-pass per capi trasparenti
- Cache `_prep` in memoria (future condivise, max 48): crop_screenshot (`_person_cropped`), keypoints multipass, `_half_body(person_path)`, `_feet_extend(person_path)`, skeleton gambe (ora dal crop originale: gambe congelate nel pass 1 = stessa posa)
- `_clean_floor`: 1 sola chiamata debris_boxes
- Log "timing ...": prep, variante render/final-check, varianti totali, multipass pass1/pass2/QC/totale, pulizia pavimento, anti-artefatto, totale prova

## 2026-11-15 (7) — X su "IL CAPO" (Studio) (DONE, testato in anteprima)
- Studio.jsx UploadBox: X (stile multi-brand) in alto a destra quando c'è un capo -> mini pop-up ClearMenu: "Vuoi eliminare il capo? Sì" (svuota solo lo slot) / "Vuoi sostituire il capo? Sì" (apre subito il selettore file). Foto in posa/Avatar intatti, stessa pagina
- testid: upload-garment-clear, upload-garment-clear-menu, upload-garment-delete-btn, upload-garment-replace-btn

## 2026-11-15 (8) — Interruttore "SERVER ESTERNO TRASPARENZE" anche sul capo unico (DONE, testato in anteprima)
- Studio.jsx: TransparentSwitch (owner) sopra IL CAPO, testid single-transparent-ext-*; stesso interruttore globale del multi-brand, le due copie restano sincronizzate (evento transparent-ext-changed)
- Backend già pronto: /tryon/generate usa `_system_with_lace` come il multi-brand (capo trasparente rilevato + interruttore ON -> server esterno solo per il pizzo)

## 2026-11-15 (9) — Server trasparenze senza limite + regola CONTINUITÀ (DONE)
- Tolti TRANSP_EXT_MAX, contatore used/max e la scritta "prove rimaste": l'interruttore resta ON finché lo spegne l'owner (credito fal.ai del suo account)
- `_ext_credit_guard` sugli endpoint tryon/outfit/grid: interruttore ON + capo trasparente -> `fal_tryon.credit_ok` (chiamata minima 1 token); senza credito -> 409 "Credito esaurito", la generazione non parte
- Prompt CONTINUITY (niente buchi/tagli/lembi volanti, giunzioni chiuse, tessuto trasparente sempre presente) + flag QC holes_or_gaps

## 2026-11-15 (10) — Posa 7 spiaggia: tolte le 2 braccia in più (DONE, 1 generazione di zona)
- Outfit 38b3cc55 (vestito pizzo nero): zona busto/ginocchia rifatta (script /app/memory/p9/arms_fix.py) -> solo le 2 braccia alzate, vestito continuo, ginocchia vuote. Originale in result_before_arms_fix
- Prompt ANTI-ARTIFACT: esattamente 2 braccia/mani/gambe/piedi, mai arti inventati; QC local_artifacts + artifact_boxes segnalano arti in più

## 2026-11-15 (11) — REGOLA FISSA IN GINOCCHIO salvata + rifatta foto 2590c974 (PARZIALE)
- Prompt KNEELING POSE in DRESSING_RULE (ginocchia a terra simmetriche, busto frontale, 2 braccia alzate, 1 piede per gamba, niente piedi soli, abiti che seguono il corpo)
- Rifatta da zero la prova (stessi capi: top pizzo rosso, jeans ricamati, décolleté rosse) -> outfit 85bfa2d1. Limite: la posa resta bloccata sulla foto base 396bf1a9 (seduta sui talloni, gambe di lato, busto 3/4) -> busto non frontale, tallone rosso ancora dietro, maniche con bordi tagliati
- Osservato: su questa foto base 2 varianti su 3 falliscono sempre con "Image generation failed: no image" (probabile rifiuto del modello) -> 1 sola variante utile
- Nota: i job in background vanno lanciati con setsid (un timeout del tool uccide il processo)

## 2026-11-15 (12) — DOPPIA RAGAZZA (miniatura) — causa trovata e corretta
- Causa: correzione zona anti-artefatto riceveva la foto intera come IMAGE 2 e il modello la ricopiava in piccolo dentro la zona -> miniatura incollata (log: registered scale 0.126)
- Fix: niente più foto intera alla correzione zona; risposta accettata solo se è lo stesso ritaglio (registrazione zoom 0.8-1.25) e senza volti nuovi (YuNet), altrimenti la zona resta com'era. Passaggio gambe: stessa verifica + 1 nuovo tentativo, poi variante scartata
- sheer_low (salto correzione gambe) ora solo per capi bassi veri (bottom/dress/suit), non per scarpe in rete
- Prompt POSE LOCKED + ONE PERSON; controllo finale: più persone / miniatura / corpo spezzato = outfit incompleto
- Rifatta outfit 9316239f -> d362fa21 (una sola ragazza, posa base, corpo intero). Resta un lembo nero che penzola sull'orlo sinistro della maglia

## 2026-11-15 (13) — Ginocchio alzato VIETATO (DONE, verificato offline)
- Prompt KNEELING: entrambe le ginocchia a terra piegate sotto il corpo, piedi dietro; vietati ginocchio alzato, piede piatto davanti a 90°, accovacciata, affondo, gamba avanti
- `_knee_raised` (multipass, dopo il passaggio gambe): se nell'originale le cosce vanno giù (inginocchiata, >=0.45) e nel risultato una coscia è orizzontale/su (<0.25) -> gambe rifatte 1 volta con LEGS_POSE_NOTE, poi variante scartata. Verificato: terza posa (legs_raw_6bd803 = -0.53) bloccata, foto giuste (0.67-0.71) passano; pose sedute non controllate

## 2026-11-15 (14) — Posa in ginocchio di RIFERIMENTO salvata + maglia ricucita (DONE, 2 generazioni di zona)
- Outfit b9426b0d (maglia nera LIU JO, jeans ricamati, piedi nudi, foto base d7170eb9): maglia completata sul fianco destro e orlo davanti chiuso (script p9/shirt_fix*.py, solo zone) -> nuovo result; originale in result_before_shirt_fix
- db.pose_references {_id:'kneeling'}: foto/regola di riferimento della posa in ginocchio
- Prompt KNEELING: mani/braccia come in IMAGE 1 (alzate o abbassate come richiesto), non più fisse in alto
- Lezione: anche negli script manuali MAI passare la foto intera come IMAGE 2 alle correzioni di zona (crea la miniatura)

## 2026-11-15 (15) — Buchi chiusi in locale + ginocchio al mare a piedi nudi (DONE, verificato senza generare)
- Controllo finale: holes_or_gaps ora fa partire la correzione LOCALE (stesso tessuto/colore), mai rigenerazione intera; artifact_boxes cerca anche buchi (manica-spalla, maglia-pantaloni, gomito, gomito interno-fianco)
- `_is_kneeling` (cache): coscia giù + caviglia all'altezza del ginocchio. `_pose_rules`: in ginocchio senza scarpe richieste -> PIEDI NUDI nella sabbia di default; con scarpe -> 2 passi (prima piedi sotto le ginocchia, poi scarpe sopra), mai scarpe sui jeans
- In ginocchio + scarpe sbagliate (shoes_wrong) -> zona piedi rifatta a piedi nudi (BAREFOOT_PROMPT, `_feet_boxes`) + avviso "Posa in ginocchio con scarpe: può avere piccoli difetti, la versione consigliata è senza scarpe" (notice via _NOTES)

## 2026-11-15 (16) — Correzioni di zona scarpe/maniche, controllo dopo pizzo, MODALITÀ EDIT (DONE, verificato senza generare)
- `_old_clothes_loop`: shoes_wrong / sleeves_detached / holes / artifacts -> correzione di ZONA anche se l'outfit è completo. Zone AI (artifact_boxes, ora anche tacco mancante, scarpa distorta, manica con pezzo mancante); se 0 zone -> `_feet_boxes` + `_arm_boxes` (keypoints). Zona piedi guidata dalla foto prodotto della scarpa scelta ORA (REF_NOTE: stesso modello, mai un altro)
- `_system_with_lace`: se lace_layer non applica (registration/pose failed) -> risultato del sistema; altrimenti controllo finale su entrambe e pizzo tenuto solo se non peggiora
- MODALITÀ EDIT (owner): POST /tryons|/outfits/{id}/retry {mode:"edit", zones:[viso,scarpe,maniche,busto,gambe]} -> parte dal result_path, rifà solo le zone (ref: viso originale / foto prodotto), resto copiato pixel per pixel; non consuma la riprova gratuita. UI: pannello "Modalità edit" in FreeRetry (testid edit-zones-panel, edit-zone-*, edit-zones-confirm)
- Punto 4 (avviso capi diversi dalla prova di riferimento): IN ATTESA di chiarimento
