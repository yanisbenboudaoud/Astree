/**
 * Contrat JSON produit par le pipeline (REFERENCE_DU_PROJET.md, section 5 ; contrat/schema_sortie.json).
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

/** Réplique (#189) : l'argument du camp adverse visé, par son numéro (1, 2…) dans la liste de ce camp. */
export interface RepondA {
  cote: 'requisitoire' | 'plaidoirie';
  numero: number;
}

export interface ArgumentContrat {
  etiquette: EtiquetteContrat;
  texte: string;
  pieces: string[];
  repond_a?: RepondA;
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
  /** Heure de l'étape, UTC (#189). Absente des procès enregistrés avant. */
  horodatage?: string;
}

/** Appels Amazon Bedrock du procès, comptés par Python (#189). Absent des procès enregistrés avant. */
export interface BedrockContrat {
  modele: string;
  appels: number;
  jetons_entree: number;
  jetons_sortie: number;
  duree_bedrock_s: number;
  cout_estime_usd: number;
  duree_proces_s: number;
  par_agent: { agent: string; appels: number; jetons_entree: number; jetons_sortie: number }[];
  garde_fou?: { verifications: number; interventions: number };
}

/**
 * Réponse de `POST /progression` (#90, pipeline/progression.py) : la progression d'un procès
 * en cours, ou son contrat quand il est archivé (`statut: "termine"`).
 */
export interface ProgressionContrat {
  id: string;
  statut: 'en_cours' | 'termine' | 'erreur';
  phase?: string | null;
  activite?: string | null;
  etapes?: EtapeTraceContrat[];
  erreur?: string;
  contrat?: ContratTribunal;
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
  sources: SourceContrat[];
  limites: string[];
  trace: EtapeTraceContrat[];
  avertissement: string;
  contre_interrogatoire?: EchangeContrat[];
  bedrock?: BedrockContrat;
}

/**
 * Une source du procès (#111). Les procès enregistrés avant #111 n'ont que `nom`, `fichier`
 * et `date_extraction` ; depuis, chaque source dit à quoi elle sert et quelles pièces
 * l'utilisent, avec la raison de l'orchestrateur (ou d'office).
 */
export interface SourceContrat {
  nom: string;
  fichier?: string;
  date_extraction?: string;
  format?: string;
  usage?: string;
  pieces?: { id: string; raison?: string }[];
  controles?: string[];
}

export type VerdictContrat = 'maintenu' | 'modifie' | 'pacte_ajuste';
