/**
 * Mode de l'interface (#137) : démonstration (données précalculées, procès enregistrés) ou direct
 * (Lambda du Tribunal). Il est choisi au chargement de la page, dans cet ordre :
 * 1. `?mode=demo` ou `?mode=direct` dans l'adresse (mémorisé pour les visites suivantes) ;
 * 2. le mode mémorisé dans localStorage (interrupteur du bandeau, ou `?mode=` d'une visite précédente) ;
 * 3. le mode de la construction (`VITE_USE_MOCKS`, voir frontend/README.md).
 * Sans adresse de Lambda (`VITE_API_URL` vide), seule la démonstration existe.
 *
 * Changer de mode recharge l'interface sur l'accueil (`changerMode`) : le mode reste donc fixe
 * pendant toute la vie de la page, et aucun procès ni état de l'autre mode ne reste en mémoire.
 */
export type ModeInterface = 'direct' | 'demo';

export const URL_API = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
/** Mode choisi à la construction du site : le défaut, quand ni l'adresse ni le navigateur n'en donnent un. */
export const MODE_CONSTRUCTION: ModeInterface = import.meta.env.VITE_USE_MOCKS === 'false' ? 'direct' : 'demo';
/** Le mode direct n'est proposé que si l'adresse de la Lambda est connue. */
export const DIRECT_DISPONIBLE = URL_API !== '';
export const CLE_MODE = 'astree.mode';

const estMode = (valeur: unknown): valeur is ModeInterface => valeur === 'direct' || valeur === 'demo';

/** Mode demandé par l'adresse (`?mode=demo` ou `?mode=direct`), sinon null. */
export function modeDemande(recherche: string): ModeInterface | null {
  const valeur = new URLSearchParams(recherche).get('mode');
  return estMode(valeur) ? valeur : null;
}

interface EntreesMode {
  /** `window.location.search` */
  recherche: string;
  memorise: string | null;
  construction: ModeInterface;
  directDisponible: boolean;
}

/** Mode de la page : adresse, sinon mode mémorisé, sinon construction ; démonstration sans Lambda. */
export function choisirMode({ recherche, memorise, construction, directDisponible }: EntreesMode): ModeInterface {
  if (!directDisponible) return 'demo';
  return modeDemande(recherche) ?? (estMode(memorise) ? memorise : construction);
}

/** Mode mémorisé, ou null (rien de mémorisé, ou localStorage indisponible : navigation privée, bloqué). */
export function lireModeMemorise(): ModeInterface | null {
  try {
    const valeur = localStorage.getItem(CLE_MODE);
    return estMode(valeur) ? valeur : null;
  } catch {
    return null;
  }
}

/** Mémorise le mode ; sans localStorage, le site marche quand même (le mode de la construction revient). */
export function memoriserMode(mode: ModeInterface): void {
  try {
    localStorage.setItem(CLE_MODE, mode);
  } catch {
    /* stockage indisponible : rien à faire */
  }
}

/** Lu une fois, au chargement de la page ; un `?mode=` valide est mémorisé. */
function modeAuChargement(): ModeInterface {
  const recherche = typeof window === 'undefined' ? '' : window.location.search;
  const mode = choisirMode({ recherche, memorise: lireModeMemorise(), construction: MODE_CONSTRUCTION, directDisponible: DIRECT_DISPONIBLE });
  if (DIRECT_DISPONIBLE && modeDemande(recherche)) memoriserMode(mode);
  return mode;
}

/** Mode de cette page. */
export const MODE: ModeInterface = modeAuChargement();
export const MODE_DIRECT = MODE === 'direct';

/**
 * Clé de sessionStorage propre au mode : un procès, un verdict ou un profil créé en direct ne
 * réapparaît pas dans les procès enregistrés, ni l'inverse. La démonstration garde la clé d'origine.
 */
export function cleSession(base: string): string {
  return MODE_DIRECT ? `${base}.direct` : base;
}

/** Passe dans l'autre mode : mémorisé, puis l'interface est rechargée sur l'accueil. */
export function changerMode(mode: ModeInterface, aller: (adresse: string) => void = (a) => window.location.assign(a)): void {
  memoriserMode(mode);
  // `?mode=` porte aussi le choix quand localStorage est indisponible.
  aller(`${import.meta.env.BASE_URL}?mode=${mode}`);
}

/** 429 sans message de la Lambda : AWS refuse l'appel (concurrence réservée de 2, coûts Bedrock). */
export const MESSAGE_TRIBUNAL_OCCUPE =
  'Le Tribunal est occupé : deux procès au plus en même temps, et un nombre limité de procès, de questions et de vérifications par minute. Réessayez dans un instant.';

/**
 * Message d'une réponse en erreur de la Lambda : son champ « erreur », sinon un message générique.
 * Un 429 vient soit d'une limite de débit de la Lambda (/tribunal, /question, /verifier, /profil :
 * son message donne le seuil), soit d'AWS quand deux procès sont déjà en cours (sans « erreur »).
 */
export async function lireErreur(reponse: Response): Promise<string> {
  let message: string | undefined;
  try {
    const corps = await reponse.json();
    if (corps && typeof corps.erreur === 'string') message = corps.erreur;
  } catch {
    /* corps illisible : message générique ci-dessous */
  }
  if (message) return message;
  return reponse.status === 429 ? MESSAGE_TRIBUNAL_OCCUPE : `Le Tribunal a répondu ${reponse.status}`;
}
