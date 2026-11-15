/**
 * Contrat JSON produit par le pipeline (CLAUDE.md, section 5 ; contrat/schema_sortie.json).
 * Les valeurs sont des décimales brutes ; seul `valeur_affichee` est prêt à afficher.
 */

export type StatutContrat = 'conforme' | 'violation' | 'a_verifier';
export type EtiquetteContrat = 'fait' | 'hypothese' | 'fictif';

export interface LignePanier {
  ticker: string;
  poids: number;
}

export type DecisionContrat =
  | { type: 'position'; ticker: string; taille: number; financement: string; libelle?: string }
  | { type: 'reallocation'; panier: LignePanier[]; part_reallouee: number; libelle?: string };

export interface RegleContrat {
  id: string;
  type: 'pire_baisse_max' | 'plafond' | 'critere_documentaire' | 'qualitative';
  libelle: string;
  seuil?: number;
  categories?: string[];
  max?: number;
  critere?: string;
}

export interface PieceContrat {
  id: string;
  type: 'calculee' | 'documentaire';
  etiquette: EtiquetteContrat;
  titre: string;
  outil: string;
  valeurs: Record<string, unknown>;
  valeur_affichee: string;
  source: string;
  traitement: string;
  limites: string;
}

export interface ArgumentContrat {
  etiquette: EtiquetteContrat;
  texte: string;
  pieces: string[];
}

export interface ControleContrat {
  statut: StatutContrat;
  regle: string;
  message: string;
  pieces?: string[];
}

export interface ArgumentRejeteContrat extends ArgumentContrat {
  cote: 'requisitoire' | 'plaidoirie';
  raison: string;
}

export interface EtapeTraceContrat {
  etape: string;
  outil?: string;
  raison?: string;
  entree?: unknown;
  sortie?: unknown;
}

export interface IndicateursContrat {
  rendement_annuel: number;
  volatilite_annuelle: number;
  pire_baisse: number;
  rendement_2022: number;
}

export interface ContratTribunal {
  persona: string;
  demande: string;
  decision: DecisionContrat;
  pacte: {
    id: string;
    profil_risque: string;
    horizon_ans: (number | null)[];
    date_signature: string;
    regles: RegleContrat[];
  };
  comparaison: { actuel: IndicateursContrat; apres: IndicateursContrat };
  taille_max_compatible: number | null;
  pieces: PieceContrat[];
  requisitoire: ArgumentContrat[];
  plaidoirie: ArgumentContrat[];
  controles: ControleContrat[];
  arguments_rejetes: ArgumentRejeteContrat[];
  verdict: 'maintenu' | 'modifie' | 'pacte_ajuste' | null;
  hypotheses: string[];
  sources: { nom: string; fichier?: string; date_extraction?: string }[];
  limites: string[];
  trace: EtapeTraceContrat[];
  avertissement: string;
}

export type VerdictContrat = 'maintenu' | 'modifie' | 'pacte_ajuste';
