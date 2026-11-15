/**
 * Mode de l'interface, lu une fois au démarrage (variables Vite, voir frontend/README.md) :
 * démonstration (données précalculées, procès enregistrés) ou direct (Lambda du Tribunal).
 */
export const MODE_DIRECT = import.meta.env.VITE_USE_MOCKS === 'false';
export const URL_API = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

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
