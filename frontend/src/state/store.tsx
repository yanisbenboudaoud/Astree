/**
 * État de l'interface, conservé par profil (annexe D.1) : décision en cours, panier,
 * procès, réponses du contre-interrogatoire, verdict, journal, réponses du Pacte vécu (#68). Changer de profil ne
 * perd pas l'état des autres. Copie dans sessionStorage quand elle est disponible.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react';
import type { DecisionUI, EntreeJournal, Piece, ResultatTribunal } from '../api/types';
import type { IdOption } from '../domaine/verdict';
import type { Reponse } from '../domaine/questions';
import type { ReponsesCalibrage } from '../domaine/calibrage';

export interface EtatTribunal {
  statut: 'vide' | 'chargement' | 'pret' | 'erreur' | 'non_enregistre';
  resultat?: ResultatTribunal;
  erreur?: string;
  decisionEnregistree?: DecisionUI | null;
}

export interface EtatVerdict {
  option: IdOption | null;
  justification: string;
  compris: boolean;
}

export interface EtatProfil {
  decision: DecisionUI | null;
  panier: string[];
  tribunal: EtatTribunal;
  reponses: Reponse[];
  piecesQuestions: Piece[];
  verdict: EtatVerdict;
  journal: EntreeJournal[];
  archive: { resume: string; statut: EntreeJournal['statut'] } | null;
  /** Réponses du Pacte vécu ; null tant que l'utilisateur n'a pas commencé. */
  calibrage: ReponsesCalibrage | null;
}

const VERDICT_VIDE: EtatVerdict = { option: null, justification: '', compris: false };

export const ETAT_INITIAL: EtatProfil = {
  decision: null,
  panier: [],
  tribunal: { statut: 'vide' },
  reponses: [],
  piecesQuestions: [],
  verdict: VERDICT_VIDE,
  journal: [],
  archive: null,
  calibrage: null,
};

type Action =
  | { type: 'decision'; profil: string; decision: DecisionUI | null }
  | { type: 'panier'; profil: string; tickers: string[] }
  | { type: 'tribunal'; profil: string; tribunal: EtatTribunal }
  | { type: 'reponse'; profil: string; reponses: Reponse[] }
  | { type: 'verdict'; profil: string; verdict: Partial<EtatVerdict> }
  | { type: 'signer'; profil: string; resume: string; entree: EntreeJournal }
  | { type: 'annuler_signature'; profil: string }
  | { type: 'calibrage'; profil: string; calibrage: ReponsesCalibrage | null };

type Etat = Record<string, EtatProfil>;

const memeDecision = (a: DecisionUI | null, b: DecisionUI | null) => JSON.stringify(a) === JSON.stringify(b);

function reducteur(etat: Etat, action: Action): Etat {
  const courant = { ...ETAT_INITIAL, ...etat[action.profil] };
  let suivant: EtatProfil;
  switch (action.type) {
    case 'decision':
      suivant = memeDecision(courant.decision, action.decision)
        ? courant
        : { ...courant, decision: action.decision, tribunal: { statut: 'vide' }, reponses: [], piecesQuestions: [], verdict: VERDICT_VIDE };
      break;
    case 'panier':
      suivant = { ...courant, panier: action.tickers };
      break;
    case 'tribunal':
      suivant = { ...courant, tribunal: action.tribunal };
      break;
    case 'reponse':
      suivant = {
        ...courant,
        reponses: [...courant.reponses, ...action.reponses],
        piecesQuestions: [...courant.piecesQuestions, ...action.reponses.flatMap((r) => r.nouvellesPieces ?? [])],
      };
      break;
    case 'verdict':
      suivant = { ...courant, verdict: { ...courant.verdict, ...action.verdict } };
      break;
    case 'signer':
      suivant = {
        ...courant,
        journal: [{ ...action.entree, nouveau: true }, ...courant.journal.map((e) => ({ ...e, nouveau: false }))],
        archive: { resume: action.resume, statut: action.entree.statut },
      };
      break;
    case 'calibrage':
      // Le Pacte change : le procès et le verdict en cours ne valent plus.
      suivant = { ...courant, calibrage: action.calibrage, tribunal: { statut: 'vide' }, reponses: [], piecesQuestions: [], verdict: VERDICT_VIDE };
      break;
    case 'annuler_signature':
      suivant = { ...courant, journal: courant.journal.filter((e) => !e.nouveau), archive: null };
      break;
    default:
      return etat;
  }
  return suivant === courant ? etat : { ...etat, [action.profil]: suivant };
}

const CLE_STOCKAGE = 'astree.etat.v1';

function lireStockage(): Etat {
  try {
    const brut = sessionStorage.getItem(CLE_STOCKAGE);
    return brut ? (JSON.parse(brut) as Etat) : {};
  } catch {
    return {};
  }
}

interface ValeurContexte {
  etat: Etat;
  envoyer: (action: Action) => void;
}

const Contexte = createContext<ValeurContexte | null>(null);

export function FournisseurEtat({ children, initial }: { children: ReactNode; initial?: Etat }) {
  const [etat, envoyer] = useReducer(reducteur, initial ?? {}, (i) => (initial ? i : lireStockage()));
  useEffect(() => {
    try {
      const copie = Object.fromEntries(Object.entries(etat).map(([id, e]) => [
        id,
        e.tribunal.statut === 'chargement' ? { ...e, tribunal: { statut: 'vide' } } : e,
      ]));
      sessionStorage.setItem(CLE_STOCKAGE, JSON.stringify(copie));
    } catch {
      /* stockage indisponible (navigation privée, quota) : l'état reste en mémoire */
    }
  }, [etat]);
  const valeur = useMemo(() => ({ etat, envoyer }), [etat]);
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useEtatProfil(idProfil: string) {
  const contexte = useContext(Contexte);
  if (!contexte) throw new Error('useEtatProfil doit être utilisé sous <FournisseurEtat>');
  const { etat, envoyer } = contexte;
  const etatProfil = useMemo(() => ({ ...ETAT_INITIAL, ...etat[idProfil] }), [etat, idProfil]);

  const definirDecision = useCallback((decision: DecisionUI | null) => envoyer({ type: 'decision', profil: idProfil, decision }), [envoyer, idProfil]);
  const definirPanier = useCallback((tickers: string[]) => envoyer({ type: 'panier', profil: idProfil, tickers }), [envoyer, idProfil]);
  const definirTribunal = useCallback((tribunal: EtatTribunal) => envoyer({ type: 'tribunal', profil: idProfil, tribunal }), [envoyer, idProfil]);
  const ajouterReponse = useCallback((...reponses: Reponse[]) => envoyer({ type: 'reponse', profil: idProfil, reponses }), [envoyer, idProfil]);
  const modifierVerdict = useCallback((verdict: Partial<EtatVerdict>) => envoyer({ type: 'verdict', profil: idProfil, verdict }), [envoyer, idProfil]);
  const signer = useCallback((resume: string, entree: EntreeJournal) => envoyer({ type: 'signer', profil: idProfil, resume, entree }), [envoyer, idProfil]);
  const annulerSignature = useCallback(() => envoyer({ type: 'annuler_signature', profil: idProfil }), [envoyer, idProfil]);
  const definirCalibrage = useCallback((calibrage: ReponsesCalibrage | null) => envoyer({ type: 'calibrage', profil: idProfil, calibrage }), [envoyer, idProfil]);

  return { etat: etatProfil, definirDecision, definirPanier, definirTribunal, ajouterReponse, modifierVerdict, signer, annulerSignature, definirCalibrage };
}
