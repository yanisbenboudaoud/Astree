/**
 * Filtrage de la recherche d'actifs (annexe D.3) : par début de mot dans le nom
 * ou par début de ticker, insensible aux accents et à la casse.
 */
import type { Titre } from '../api/types';

export function normaliser(texte: string): string {
  return texte.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function debutDeMot(nom: string, requete: string): number {
  const n = normaliser(nom);
  const motif = new RegExp(`(^|[^a-z0-9])${requete.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`);
  const trouve = motif.exec(n);
  if (!trouve) return -1;
  return trouve.index + trouve[1].length;
}

export interface ResultatRecherche {
  titre: Titre;
  /** Position et longueur de la partie tapée dans le nom affiché (pour la mettre en gras). */
  surligne: { debut: number; longueur: number } | null;
}

export function rechercherTitres(titres: Titre[], requeteBrute: string): ResultatRecherche[] {
  const requete = normaliser(requeteBrute.trim());
  if (!requete) return [];
  const resultats: ResultatRecherche[] = [];
  for (const titre of titres) {
    const dansNom = debutDeMot(titre.nom, requete);
    const dansOriginal = debutDeMot(titre.nomOriginal, requete);
    const dansTicker = normaliser(titre.ticker).startsWith(requete);
    if (dansNom >= 0 || dansOriginal >= 0 || dansTicker) {
      resultats.push({ titre, surligne: dansNom >= 0 ? { debut: dansNom, longueur: requete.length } : null });
    }
  }
  // Les titres dont le ticker commence par la requête d'abord, puis l'ordre alphabétique des noms.
  return resultats.sort((a, b) => {
    const ta = normaliser(a.titre.ticker).startsWith(requete) ? 0 : 1;
    const tb = normaliser(b.titre.ticker).startsWith(requete) ? 0 : 1;
    return ta - tb || a.titre.nom.localeCompare(b.titre.nom, 'fr-CA');
  });
}
