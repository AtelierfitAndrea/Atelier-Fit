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
