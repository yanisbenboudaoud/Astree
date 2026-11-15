/**
 * Explication d'une pièce à conviction pour l'utilisateur : ce qu'elle montre
 * et comment lire son chiffre, selon l'outil Python qui l'a produite.
 * Aucun chiffre ici : les valeurs restent celles de la pièce.
 */
import type { Piece } from '../api/types';

/** Ce qu'est une pièce, dit une fois pour toutes. */
export const DEFINITION_PIECE =
  'Les pièces sont les preuves du procès, numérotées P1, P2, P3… dans l’ordre où le Tribunal les a réunies. '
  + 'Chacune est un résultat calculé par Python à partir des données, un document public ou une réponse de l’investisseur. '
  + 'Le Procureur et l’Avocat ne peuvent citer que ces pièces, et le Greffier vérifie que chaque chiffre cité s’y trouve.';

export interface GuidePiece {
  /** Ce que montre la pièce, en une phrase. */
  role: string;
  /** Comment lire le chiffre affiché, quand il n'est pas évident. */
  lecture?: string;
}

const GUIDES: Record<string, GuidePiece> = {
  charger_pacte: {
    role: 'Les règles que l’investisseur a fixées à l’avance (son Pacte). Le Tribunal juge la décision contre ces règles.',
    lecture: 'La date est celle de la signature du Pacte.',
  },
  simuler_portefeuille: {
    role: 'Ce qu’aurait donné le portefeuille avec la décision, rejoué jour par jour sur les 5 dernières années.',
    lecture: '« max » : la pire baisse depuis un sommet. « /an » : le rendement moyen par année.',
  },
  indicateurs_actif: {
    role: 'Le comportement passé du titre seul, sur les 5 dernières années.',
    lecture: '« max » : sa pire baisse depuis un sommet. « /an » : son rendement moyen par année. Puis le temps qu’il lui a fallu pour revenir à son sommet.',
  },
  taille_max_compatible: {
    role: 'La plus grande taille de la décision qui respecterait encore toutes les règles chiffrées du Pacte.',
  },
  points_de_bascule: {
    role: 'Ce qui changerait la réponse : pour chaque règle en violation, la taille à ne pas dépasser, ou le seuil du Pacte qui suffirait.',
    lecture: '« 9 % max » : la plus grande taille conforme. « seuil » ou « plafond » : la limite qu’il faudrait accepter dans le Pacte.',
  },
  calculer_correlations: {
    role: 'À quel point les titres montent et baissent en même temps.',
    lecture: 'Une corrélation va de −1 à 1. Proche de 1 : les deux titres bougent ensemble, ils diversifient donc peu.',
  },
  consulter_jurisprudence: {
    role: 'Les décisions passées de ce même profil, et ce que l’investisseur a choisi à chaque fois.',
  },
  mesurer_liquidite: {
    role: 'Le nombre de jours de bourse qu’il faudrait pour revendre chaque ligne sans peser sur le marché.',
  },
  composition_fnb: {
    role: 'Ce que contiennent vraiment les fonds (FNB) du panier, catégorie par catégorie.',
  },
  rechercher_documents: {
    role: 'Un document public trouvé par l’équipe sur un critère autre que financier (ex. : ESG). Ce n’est pas un calcul : c’est un extrait cité avec sa source.',
  },
  calibrer_pacte: {
    role: 'Les réponses de l’investisseur au Pacte vécu : de vrais jours de baisse revécus, sans connaître la suite.',
    lecture: '« Reste à » : la plus forte baisse où il garde ses titres. « vend à » : la baisse où il vend.',
  },
  lire_questionnaire: {
    role: 'Les réponses de l’investisseur au questionnaire, qui ont servi à écrire son Pacte.',
  },
};

const REJEU_2022: GuidePiece = {
  role: 'Le portefeuille rejoué pendant l’année 2022, une année de forte baisse des marchés.',
  lecture: 'À gauche, le rendement de 2022 sans la décision ; à droite, avec la décision.',
};

const PAR_TYPE: Record<NonNullable<Piece['type']>, GuidePiece> = {
  calculee: { role: 'Un résultat calculé par Python à partir des données du marché.' },
  documentaire: { role: 'Un extrait de document public, cité avec sa source.' },
  declaree: { role: 'Des réponses données par l’investisseur lui-même.' },
};

export function guidePiece(piece: Pick<Piece, 'outil' | 'type' | 'titre'>): GuidePiece | null {
  if (piece.outil === 'simuler_portefeuille' && /^rejeu/i.test(piece.titre)) return REJEU_2022;
  if (piece.outil && GUIDES[piece.outil]) return GUIDES[piece.outil];
  return piece.type ? PAR_TYPE[piece.type] : null;
}

/** « P2 » → 2 ; null si le code n'est pas numéroté. */
export function numeroPiece(code: string): number | null {
  const m = /^P(\d+)$/.exec(code);
  return m ? Number(m[1]) : null;
}

/**
 * Coupe un texte de pièce (source, traitement, limites) en points courts.
 * Les pièces séparent leurs éléments par « ; » ; une virgule ou un point
 * restent dans leur élément.
 */
export function decouperEnPoints(texte: string | undefined): string[] {
  if (!texte) return [];
  return texte
    .split(/\s*;\s*/)
    .map((t) => t.trim().replace(/\.$/, ''))
    .filter(Boolean)
    .map((t) => t.charAt(0).toLocaleUpperCase('fr') + t.slice(1));
}
