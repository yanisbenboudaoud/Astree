/**
 * Accès au Tribunal.
 * - Mode démonstration (VITE_USE_MOCKS=true, par défaut) : rejoue un procès réellement tenu
 *   par la Lambda et archivé dans S3 (copié dans src/data/proces/), s'il juge exactement la décision.
 * - Mode direct (VITE_USE_MOCKS=false) : appelle la Lambda du Tribunal (VITE_API_URL),
 *   `POST /tribunal` puis `POST /verdict` (deploiement/lambda_tribunal.py).
 * - Dans les deux modes, « Trompez le Greffier » appelle `POST /verifier` (Python seul, sans
 *   Bedrock) et une question libre appelle `POST /question` (Bedrock) sur le procès affiché,
 *   dès que VITE_API_URL est défini.
 */
import indexProces from '../data/proces/index.json';
import type { ContratTribunal, DecisionContrat, EchangeContrat, PieceContrat, VerdictContrat } from './contrat';
import type { DecisionUI, ResultatTribunal, ResultatVerification } from './types';
import type { Reponse } from '../domaine/questions';
import { adapterContrat, adapterEchange, numeroAudience } from './adaptateur';
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
  procesId: string;
  profil: string;
  note?: string;
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

interface ProcesEnregistre {
  contrat: ContratTribunal;
  procesId: string;
}

/**
 * Procès enregistrés d'un profil, dans l'ordre de l'index (le premier est la décision de démonstration).
 * Avec le Pacte vécu (#68), seuls ceux tenus avec ses réponses ; sans lui, seuls les autres.
 */
async function procesEnregistres(idProfil: string, avecCalibrage = false): Promise<ProcesEnregistre[]> {
  const entrees = (indexProces.proces as EntreeIndex[]).filter((p) => p.profil === idProfil && Boolean(p.calibrage) === avecCalibrage);
  const charges = await Promise.all(entrees.map(async (entree) => {
    const chargeur = contratsEnregistres[`../data/proces/${entree.procesId}.json`];
    return chargeur ? { contrat: await chargeur(), procesId: entree.procesId } : null;
  }));
  return charges.filter((p): p is ProcesEnregistre => p !== null);
}

/** Décision jugée par le premier procès enregistré d'un profil (pour proposer de la rejouer). */
export async function decisionEnregistree(idProfil: string): Promise<DecisionUI | null> {
  const [premier] = await procesEnregistres(idProfil);
  return premier ? decisionDepuisContrat(premier.contrat.decision) : null;
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
    const enregistres = await procesEnregistres(idProfil, Boolean(calibrage));
    if (calibrage) {
      // Seul un procès tenu avec exactement ces réponses peut être rejoué : aucun procès n'est inventé.
      const memes = enregistres.filter((p) => {
        const reponses = reponsesDuContrat(p.contrat);
        return reponses !== null && memesReponses(calibrage, reponses);
      });
      if (!memes.length) {
        throw new ProcesNonEnregistre(
          null,
          'Le procès enregistré avec le Pacte vécu utilise les réponses de démonstration du profil. Avec vos propres réponses, il faut le Tribunal en direct.',
        );
      }
      enregistres.splice(0, enregistres.length, ...memes);
    }
    const juge = enregistres.find((p) => correspondAuContrat(decision, p.contrat.decision));
    if (!juge) throw new ProcesNonEnregistre(enregistres[0] ? decisionDepuisContrat(enregistres[0].contrat.decision) : null);
    return adapterContrat(juge.contrat, { ...contexte, audience: numeroAudience(juge.procesId), procesId: juge.procesId });
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

/** « Trompez le Greffier » possible : le procès a un identifiant S3 et l'adresse de la Lambda est connue. */
export function greffierEnDirect(procesId: string | undefined): boolean {
  return Boolean(URL_API && procesId);
}

/**
 * Fait vérifier par le Greffier (`POST /verifier`, outil 6, sans Bedrock) un argument tapé à la main,
 * contre les pièces citées du procès archivé. Renvoie aussi la durée mesurée de l'aller-retour.
 */
export async function verifierArgument(procesId: string, texte: string, pieces: string[]): Promise<ResultatVerification> {
  if (!URL_API) throw new Error('Adresse du Tribunal absente : définissez VITE_API_URL (Function URL de la Lambda).');
  const debut = performance.now();
  const reponse = await fetch(`${URL_API}/verifier`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: procesId, texte, pieces }),
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  const resultat = (await reponse.json()) as Omit<ResultatVerification, 'dureeMs'>;
  return { ...resultat, dureeMs: Math.round(performance.now() - debut) };
}

/**
 * Contre-interrogatoire (`POST /question`, #55) : l'orchestrateur Bedrock choisit ses outils,
 * le Procureur et l'Avocat répondent avec les pièces, le Greffier vérifie chaque chiffre.
 * Le procès archivé dans S3 est complété : une question suivante peut citer les nouvelles pièces.
 */
export async function poserQuestion(procesId: string, question: string): Promise<Reponse[]> {
  if (!URL_API) throw new Error('Adresse du Tribunal absente : définissez VITE_API_URL (Function URL de la Lambda).');
  const reponse = await fetch(`${URL_API}/question`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: procesId, question }),
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  const corps = (await reponse.json()) as { echange: EchangeContrat; pieces: PieceContrat[] };
  return adapterEchange(corps.echange, corps.pieces);
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
