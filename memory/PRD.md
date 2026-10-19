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
