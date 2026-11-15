/**
 * Mode de l'interface, lu une fois au démarrage (variables Vite, voir frontend/README.md) :
 * démonstration (données précalculées, procès enregistrés) ou direct (Lambda du Tribunal).
 */
export const MODE_DIRECT = import.meta.env.VITE_USE_MOCKS === 'false';
export const URL_API = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

/** Message d'une réponse en erreur de la Lambda : son champ « erreur », sinon le statut HTTP. */
export async function lireErreur(reponse: Response): Promise<string> {
  if (reponse.status === 429) {
    // Concurrence réservée de 2 (coûts Bedrock) ou limite de débit de /verifier et /profil.
    return 'Le Tribunal est occupé : deux procès au plus en même temps, et un nombre limité de vérifications par minute. Réessayez dans un instant.';
  }
  try {
    const corps = await reponse.json();
    if (corps && typeof corps.erreur === 'string') return corps.erreur;
  } catch {
    /* corps illisible : message générique ci-dessous */
  }
  return `Le Tribunal a répondu ${reponse.status}`;
}
