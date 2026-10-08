import { createContext, useContext, useEffect, useMemo, useState } from "react";

const DICTIONARIES = {
  it: {
    nav: { home: "Home", studio: "Studio", wardrobe: "Armadio", profile: "Profilo" },
    accuracy: {
      label: "Fitting Accuracy",
      reliable: "Affidabile",
      yes: "SÌ",
      no: "NO",
      tooltipTitle: "Attenzione",
      tooltipBody: "Profilo non affidabile per reso garantito. Completa misure e aggiorna il peso.",
      updateNow: "Aggiorna ora",
    },
    weight: {
      banner: "Controllo peso",
      stale: "Attenzione: Fit non affidabile — Aggiorna peso",
      due: "Aggiorna il tuo peso per mantenere il fit perfetto",
      start: "Registra il tuo peso per iniziare — lo controlliamo ogni 2 mesi",
      modalTitle: "Aggiorna il tuo peso",
      modalHint: "Serve per mantenere taglie accurate e profilo affidabile per i brand partner.",
      field: "Peso (kg)",
      save: "Salva",
      cancel: "Annulla",
      invalid: "Inserisci un peso valido in kg",
      saved: "Peso aggiornato!",
      serverError: "Salvataggio sul server non riuscito",
    },
    dashboard: {
      welcome: "Bentornato",
      hiAgain: "Ciao di nuovo,",
      fallbackName: "amica",
      heroCopy: "Il tuo camerino è pronto. Avvia una nuova prova o rivedi un look salvato nel tuo atelier.",
      newTryOn: "Nuova prova",
      cards: {
        measurementsLabel: "Misurazioni",
        measurementsValue: "Le tue misure",
        measurementsCtaAdd: "Aggiungi",
        measurementsCtaUpdate: "Aggiorna",
        wardrobeLabel: "Armadio verificato",
        wardrobeUnit: "capi",
        wardrobeCta: "Apri armadio",
        studioLabel: "Studio di prova",
        studioValue: "Pronto",
        studioCta: "Entra nello studio",
      },
      recent: "Prove recenti",
      atelier: "Il tuo atelier",
      seeAll: "Vedi tutto",
      emptyTitle: "Atelier vuoto",
      emptyBody: "Nessuna prova ancora. Vai allo Studio per vedere come ti sta il tuo prossimo capo preferito.",
      openStudio: "Apri lo Studio",
      untitled: "Senza titolo",
      piece: "capo",
    },
  },
  en: {
    nav: { home: "Home", studio: "Studio", wardrobe: "Wardrobe", profile: "Profile" },
    accuracy: {
      label: "Fitting Accuracy",
      reliable: "Reliable",
      yes: "YES",
      no: "NO",
      tooltipTitle: "Attention",
      tooltipBody: "Profile not reliable for guaranteed returns. Complete measurements and update your weight.",
      updateNow: "Update now",
    },
    weight: {
      banner: "Weight check",
      stale: "Warning: unreliable fit — Update your weight",
      due: "Update your weight to keep a perfect fit",
      start: "Record your weight to begin — we check it every 2 months",
      modalTitle: "Update your weight",
      modalHint: "Keeps sizes accurate and your profile reliable for partner brands.",
      field: "Weight (kg)",
      save: "Save",
      cancel: "Cancel",
      invalid: "Enter a valid weight in kg",
      saved: "Weight updated!",
      serverError: "Server save failed",
    },
    dashboard: {
      welcome: "Welcome back",
      hiAgain: "Hello again,",
      fallbackName: "friend",
      heroCopy: "Your fitting room is ready. Start a new try-on or revisit a saved look from your atelier.",
      newTryOn: "New try-on",
      cards: {
        measurementsLabel: "Measurements",
        measurementsValue: "Your sizes",
        measurementsCtaAdd: "Add",
        measurementsCtaUpdate: "Update",
        wardrobeLabel: "Verified wardrobe",
        wardrobeUnit: "pieces",
        wardrobeCta: "Open wardrobe",
        studioLabel: "Fitting studio",
        studioValue: "Ready",
        studioCta: "Enter the studio",
      },
      recent: "Recent try-ons",
      atelier: "Your atelier",
      seeAll: "See all",
      emptyTitle: "Empty atelier",
      emptyBody: "No try-ons yet. Head to the Studio to see how your next favourite piece will look on you.",
      openStudio: "Open the Studio",
      untitled: "Untitled",
      piece: "piece",
    },
  },
  fr: {
    nav: { home: "Accueil", studio: "Studio", wardrobe: "Dressing", profile: "Profil" },
    accuracy: {
      label: "Fitting Accuracy",
      reliable: "Fiable",
      yes: "OUI",
      no: "NON",
      tooltipTitle: "Attention",
      tooltipBody: "Profil non fiable pour un retour garanti. Complétez vos mesures et mettez à jour votre poids.",
      updateNow: "Mettre à jour",
    },
    weight: {
      banner: "Contrôle du poids",
      stale: "Attention : coupe non fiable — Mettez à jour votre poids",
      due: "Mettez à jour votre poids pour un ajustement parfait",
      start: "Enregistrez votre poids pour commencer — vérification tous les 2 mois",
      modalTitle: "Mettre à jour votre poids",
      modalHint: "Garde les tailles précises et le profil fiable pour les marques partenaires.",
      field: "Poids (kg)",
      save: "Enregistrer",
      cancel: "Annuler",
      invalid: "Entrez un poids valide en kg",
      saved: "Poids mis à jour !",
      serverError: "Échec de l'enregistrement sur le serveur",
    },
    dashboard: {
      welcome: "Bon retour",
      hiAgain: "Rebonjour,",
      fallbackName: "ami·e",
      heroCopy: "Votre cabine d'essayage est prête. Lancez un nouvel essayage ou revisitez un look sauvegardé.",
      newTryOn: "Nouvel essayage",
      cards: {
        measurementsLabel: "Mesures",
        measurementsValue: "Vos tailles",
        measurementsCtaAdd: "Ajouter",
        measurementsCtaUpdate: "Mettre à jour",
        wardrobeLabel: "Dressing vérifié",
        wardrobeUnit: "pièces",
        wardrobeCta: "Ouvrir le dressing",
        studioLabel: "Studio d'essayage",
        studioValue: "Prêt",
        studioCta: "Entrer dans le studio",
      },
      recent: "Essayages récents",
      atelier: "Votre atelier",
      seeAll: "Tout voir",
      emptyTitle: "Atelier vide",
      emptyBody: "Aucun essayage. Allez au Studio pour voir votre prochaine pièce préférée.",
      openStudio: "Ouvrir le Studio",
      untitled: "Sans titre",
      piece: "pièce",
    },
  },
  de: {
    nav: { home: "Start", studio: "Studio", wardrobe: "Garderobe", profile: "Profil" },
    accuracy: {
      label: "Fitting Accuracy",
      reliable: "Zuverlässig",
      yes: "JA",
      no: "NEIN",
      tooltipTitle: "Achtung",
      tooltipBody: "Profil nicht zuverlässig für garantierte Rücksendung. Maße vervollständigen und Gewicht aktualisieren.",
      updateNow: "Jetzt aktualisieren",
    },
    weight: {
      banner: "Gewichtskontrolle",
      stale: "Achtung: Passform unzuverlässig — Gewicht aktualisieren",
      due: "Gewicht aktualisieren, damit die Passform perfekt bleibt",
      start: "Dein Gewicht erfassen — wir prüfen es alle 2 Monate",
      modalTitle: "Gewicht aktualisieren",
      modalHint: "Für präzise Größen und ein zuverlässiges Profil bei Partnermarken.",
      field: "Gewicht (kg)",
      save: "Speichern",
      cancel: "Abbrechen",
      invalid: "Gib ein gültiges Gewicht in kg ein",
      saved: "Gewicht aktualisiert!",
      serverError: "Speichern auf dem Server fehlgeschlagen",
    },
    dashboard: {
      welcome: "Willkommen zurück",
      hiAgain: "Hallo wieder,",
      fallbackName: "Freund·in",
      heroCopy: "Deine Umkleide ist bereit. Starte ein neues Try-on oder öffne einen gespeicherten Look.",
      newTryOn: "Neues Try-on",
      cards: {
        measurementsLabel: "Maße",
        measurementsValue: "Deine Größen",
        measurementsCtaAdd: "Hinzufügen",
        measurementsCtaUpdate: "Aktualisieren",
        wardrobeLabel: "Verifizierte Garderobe",
        wardrobeUnit: "Teile",
        wardrobeCta: "Garderobe öffnen",
        studioLabel: "Anprobe-Studio",
        studioValue: "Bereit",
        studioCta: "Zum Studio",
      },
      recent: "Letzte Try-ons",
      atelier: "Dein Atelier",
      seeAll: "Alle ansehen",
      emptyTitle: "Atelier leer",
      emptyBody: "Noch keine Try-ons. Geh zum Studio, um dein nächstes Lieblingsstück zu sehen.",
      openStudio: "Studio öffnen",
      untitled: "Ohne Titel",
      piece: "Teil",
    },
  },
};

export const LANGS = [
  { code: "it", label: "IT", flag: "🇮🇹" },
  { code: "en", label: "EN", flag: "🇬🇧" },
  { code: "fr", label: "FR", flag: "🇫🇷" },
  { code: "de", label: "DE", flag: "🇩🇪" },
];

const I18nCtx = createContext({ lang: "it", setLang: () => {}, t: (p) => p });

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try { return localStorage.getItem("vfit_lang") || "it"; } catch { return "it"; }
  });

  const setLang = (l) => {
    setLangState(l);
    try { localStorage.setItem("vfit_lang", l); } catch (_e) { /* ignore */ }
  };

  useEffect(() => {
    document.documentElement.setAttribute("lang", lang);
  }, [lang]);

  const t = useMemo(() => {
    const dict = DICTIONARIES[lang] || DICTIONARIES.it;
    return (path) => {
      const parts = path.split(".");
      let node = dict;
      for (const p of parts) {
        if (node && typeof node === "object" && p in node) node = node[p];
        else return path;
      }
      return node;
    };
  }, [lang]);

  return <I18nCtx.Provider value={{ lang, setLang, t }}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);
