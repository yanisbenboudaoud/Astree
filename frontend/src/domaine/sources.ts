/**
 * Sources du dossier (#111) : ce que l'écran Tribunal montre de chacune.
 *
 * Plusieurs sources servent les mêmes pièces (les prix, le change et l'univers d'actifs
 * servent toutes les simulations). La raison de l'orchestrateur n'est donc écrite qu'une
 * fois, sous la première source qui utilise la pièce ; les suivantes ne montrent que la
 * pastille, pour que le bloc reste court.
 */
import type { SourceDossier } from '../api/types';

export interface SourceAffichee extends SourceDossier {
  /** Pièces dont la raison est écrite ici (première source qui les utilise). */
  expliquees: { code: string; raison: string }[];
  /** Autres pièces : déjà expliquées plus haut, ou sans raison. */
  autres: { code: string; raison?: string }[];
}

export function sourcesAffichees(sources: SourceDossier[]): SourceAffichee[] {
  const vues = new Set<string>();
  return sources.map((source) => {
    const expliquees = source.pieces.flatMap((p) => (p.raison && !vues.has(p.code) ? [{ code: p.code, raison: p.raison }] : []));
    const codesExpliques = new Set(expliquees.map((p) => p.code));
    source.pieces.forEach((p) => vues.add(p.code));
    return { ...source, expliquees, autres: source.pieces.filter((p) => !codesExpliques.has(p.code)) };
  });
}
