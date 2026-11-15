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
  /** Seuil mesuré par le Pacte vécu (#68) : d'où il vient, son étiquette et la pièce qui le prouve. */
  provenance?: string;
  etiquette?: EtiquetteContrat;
  piece?: string;
}

export interface PieceContrat {
  id: string;
  /** `declaree` : réponses de l'utilisateur au Pacte vécu (#68). */
  type: 'calculee' | 'documentaire' | 'declaree';
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

/** Ce qui rendrait conforme une règle calculable en violation (#61) : décision ramenée à `taille_max`, ou Pacte ajusté à `seuil_suffisant`. */
export interface PointDeBasculeContrat {
  regle: string;
  type: 'pire_baisse_max' | 'plafond';
  seuil_actuel: number;
  seuil_suffisant: number;
  /** Plus grande taille (ou part réallouée) où cette règle est conforme ; null si même 0 % la viole. */
  taille_max: number | null;
  /** Phrase prête à afficher, écrite par Python. */
  message: string;
  pieces: string[];
}

export interface IndicateursContrat {
  rendement_annuel: number;
  volatilite_annuelle: number;
  pire_baisse: number;
  rendement_2022: number;
}

/** Une question libre posée après le procès et ses réponses vérifiées (#55, `POST /question`). */
export interface EchangeContrat {
  question: string;
  pieces_ajoutees: string[];
  requisitoire: ArgumentContrat[];
  plaidoirie: ArgumentContrat[];
  arguments_rejetes: ArgumentRejeteContrat[];
  controle_chiffres: ControleContrat;
  trace: EtapeTraceContrat[];
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
  /** Absent des procès enregistrés avant #61. */
  points_de_bascule?: PointDeBasculeContrat[];
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
  contre_interrogatoire?: EchangeContrat[];
}

export type VerdictContrat = 'maintenu' | 'modifie' | 'pacte_ajuste';
