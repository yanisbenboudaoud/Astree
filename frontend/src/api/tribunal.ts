/**
 * Accès au Tribunal.
 * - Mode démonstration (VITE_USE_MOCKS=true, par défaut) : rejoue un procès réellement tenu
 *   par le pipeline et enregistré dans src/data/proces/, s'il juge exactement la décision.
 * - Mode direct (VITE_USE_MOCKS=false) : appelle la Lambda du Tribunal (VITE_API_URL),
 *   `POST /tribunal` puis `POST /verdict` (deploiement/lambda_tribunal.py).
 */
import indexProces from '../data/proces/index.json';
import type { ContratTribunal, DecisionContrat, VerdictContrat } from './contrat';
import type { DecisionUI, ResultatTribunal } from './types';
import { adapterContrat, numeroAudience } from './adaptateur';
import { profil as profilDe } from './donnees';
import { correspondAuContrat, demandeDecision, libelleDecision } from '../domaine/decision';

export const MODE_DIRECT = import.meta.env.VITE_USE_MOCKS === 'false';
const URL_API = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

const contratsEnregistres = import.meta.glob<ContratTribunal>('../data/proces/*.json', { import: 'default' });

export class ProcesNonEnregistre extends Error {
  constructor(public readonly decisionEnregistree: DecisionUI | null, public readonly raisonPacteVecu?: string) {
    super('Aucun procès enregistré pour cette décision');
    this.name = 'ProcesNonEnregistre';
  }
}

interface EntreeIndex {
  fichier: string;
  profil: string;
  audience: string;
  /** Procès tenu avec les réponses préenregistrées du Pacte vécu (#68). */
  calibrage?: boolean;
}

/** Réponses du Pacte vécu enregistrées dans la trace d'un procès (étape « calibrage »). */
export function reponsesDuContrat(contrat: ContratTribunal): Record<string, string> | null {
  const etape = contrat.trace.find((e) => e.etape === 'calibrage');
  const entree = etape?.entree as { questions?: string[]; reponses?: string[] } | undefined;
  if (!entree?.questions || !entree.reponses) return null;
  return Object.fromEntries(entree.questions.map((q, i) => [q, entree.reponses![i]]));
}

const memesReponses = (a: Record<string, string>, b: Record<string, string>) =>
  JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

export function decisionDepuisContrat(decision: DecisionContrat): DecisionUI {
  if (decision.type === 'position') return { type: 'position', ticker: decision.ticker, taille: Math.round(decision.taille * 100) };
  return { type: 'panier', lignes: decision.panier.map((l) => ({ ticker: l.ticker, poids: Math.round(l.poids * 100) })) };
}

async function contratEnregistre(idProfil: string, avecCalibrage = false): Promise<{ contrat: ContratTribunal; audience: string } | null> {
  const entree = (indexProces.proces as EntreeIndex[]).find((p) => p.profil === idProfil && Boolean(p.calibrage) === avecCalibrage);
  const chargeur = entree && contratsEnregistres[`../data/proces/${entree.fichier}`];
  if (!entree || !chargeur) return null;
  return { contrat: await chargeur(), audience: entree.audience };
}

/** Décision jugée par le procès enregistré d'un profil (pour proposer de la rejouer). */
export async function decisionEnregistree(idProfil: string): Promise<DecisionUI | null> {
  const enregistre = await contratEnregistre(idProfil);
  return enregistre ? decisionDepuisContrat(enregistre.contrat.decision) : null;
}

async function lireErreur(reponse: Response): Promise<string> {
  try {
    const corps = await reponse.json();
    if (corps && typeof corps.erreur === 'string') return corps.erreur;
  } catch {
    /* corps illisible : message générique ci-dessous */
  }
  return `Le Tribunal a répondu ${reponse.status}`;
}

/**
 * @param calibrage réponses du Pacte vécu (#68), quand il est terminé : en direct, la Lambda
 *   recalcule le seuil en Python ; en démonstration, seul le procès tenu avec ces mêmes
 *   réponses (celles du profil de test) peut être rejoué.
 */
export async function jugerDecision(
  idProfil: string,
  decision: DecisionUI,
  signal?: AbortSignal,
  calibrage?: Record<string, string> | null,
): Promise<ResultatTribunal> {
  const profil = profilDe(idProfil);
  const contexte = { nomProfil: profil?.nom ?? idProfil, titreDecision: libelleDecision(decision) };

  if (!MODE_DIRECT) {
    const enregistre = await contratEnregistre(idProfil, Boolean(calibrage));
    const reponsesEnregistrees = enregistre && reponsesDuContrat(enregistre.contrat);
    if (calibrage && (!reponsesEnregistrees || !memesReponses(calibrage, reponsesEnregistrees))) {
      throw new ProcesNonEnregistre(
        null,
        'Le procès enregistré avec le Pacte vécu utilise les réponses de démonstration du profil. Avec vos propres réponses, il faut le Tribunal en direct.',
      );
    }
    if (!enregistre || !correspondAuContrat(decision, enregistre.contrat.decision)) {
      throw new ProcesNonEnregistre(enregistre ? decisionDepuisContrat(enregistre.contrat.decision) : null);
    }
    return adapterContrat(enregistre.contrat, { ...contexte, audience: enregistre.audience });
  }

  if (!URL_API) throw new Error('Adresse du Tribunal absente : définissez VITE_API_URL (Function URL de la Lambda).');
  const reponse = await fetch(`${URL_API}/tribunal`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ profil: idProfil, demande: demandeDecision(decision), ...(calibrage ? { calibrage: { reponses: calibrage } } : {}) }),
    signal,
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  const contrat = (await reponse.json()) as ContratTribunal;
  const procesId = reponse.headers.get('x-proces-id') ?? undefined;
  return adapterContrat(contrat, { ...contexte, audience: numeroAudience(procesId), procesId });
}

/** Archive le verdict. En démonstration, rien n'est envoyé : le verdict reste dans le navigateur. */
export async function archiverVerdict(procesId: string | undefined, verdict: VerdictContrat): Promise<void> {
  if (!MODE_DIRECT || !procesId) return;
  const reponse = await fetch(`${URL_API}/verdict`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: procesId, verdict }),
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
}
