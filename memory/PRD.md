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
