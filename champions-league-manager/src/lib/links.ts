/** Liens externes du tournoi, regroupés pour être modifiables en un seul endroit. */
export const RULES_URL =
  "https://drive.google.com/file/d/1nXWkmwmjpurrFBCGCRhf9RYeFFiDotsx/view?usp=drivesdk";

/** Le suffixe /viewform devient /viewform?embedded=true pour l'intégration. */
export const SIGNUP_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLSfEeImAlH_s4APXG6L9HqysDoezd8PjynTHX0GUJ8EStwbCMg/viewform";

/**
 * Drive refuse d'être affiché dans un cadre depuis /view : seul /preview
 * l'autorise. Le suffixe varie selon l'origine du partage (?usp=sharing,
 * ?usp=drivesdk, parfois rien) — on remplace donc tout ce qui suit /view.
 */
export const RULES_EMBED_URL = RULES_URL.replace(/\/view(\?.*)?$/, "/preview");

export const SIGNUP_EMBED_URL = `${SIGNUP_URL}?embedded=true`;
