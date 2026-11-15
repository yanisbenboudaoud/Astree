/**
 * Accès au Tribunal.
 * - Mode démonstration (VITE_USE_MOCKS=true, par défaut) : rejoue un procès réellement tenu
 *   par la Lambda et archivé dans S3 (copié dans src/data/proces/), s'il juge exactement la décision.
 * - Mode direct (VITE_USE_MOCKS=false) : appelle la Lambda du Tribunal (VITE_API_URL),
 *   `POST /tribunal` puis `POST /verdict` (deploiement/lambda_tribunal.py). Le procès part en
 *   arrière-plan (réponse 202) et sa progression réelle est relue toutes les 1,5 s sur
 *   `POST /progression` jusqu'au contrat (#90).
 * - Dans les deux modes, « Trompez le Greffier » appelle `POST /verifier` (Python seul, sans
 *   Bedrock) sur le procès affiché, dès que VITE_API_URL est défini.
 * - En mode direct, une question libre appelle `POST /question` (contre-interrogatoire, #55).
 * Le procès-verbal (#57) est produit par Python : `POST /proces-verbal` en mode direct,
 * pages précalculées de public/proces-verbaux/<id>.html en démonstration.
 */
import indexProces from '../data/proces/index.json';
import type { ContratTribunal, DecisionContrat, EchangeContrat, PieceContrat, ProgressionContrat, VerdictContrat } from './contrat';
import type { DecisionUI, ProgressionTribunal, ResultatTribunal, ResultatVerification } from './types';
import { adapterContrat, etapeTrace, numeroAudience } from './adaptateur';
import { profil as profilDe } from './donnees';
import { correspondAuContrat, demandeDecision, libelleDecision } from '../domaine/decision';
import { estPhase } from '../domaine/progression';

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
  if (reponse.status === 429) {
    // Concurrence réservée de 2 (coûts Bedrock) ou limite de débit de /verifier.
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

export const INTERVALLE_SUIVI_MS = 1500;
export const DELAI_MAX_SUIVI_MS = 120_000;
/** Sans première phase après ce délai : Lambda à froid, ou deux procès déjà en cours. */
const DELAI_DEMARRAGE_MS = 8000;

export const AVIS_OCCUPE = 'Le Tribunal est occupé (deux procès au plus en même temps) : la progression reprendra dès qu’une place se libère.';
export const AVIS_RESEAU = 'Connexion au Tribunal interrompue : nouvelle tentative…';
export const AVIS_DEMARRAGE_LENT = 'Le démarrage prend plus de temps que d’habitude : Lambda à froid, ou deux procès déjà en cours.';

function attente(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resoudre, rejeter) => {
    if (signal?.aborted) {
      rejeter(new DOMException('Suivi interrompu', 'AbortError'));
      return;
    }
    const minuterie = setTimeout(resoudre, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(minuterie);
      rejeter(new DOMException('Suivi interrompu', 'AbortError'));
    }, { once: true });
  });
}

/** Réponse de /progression → écran : les étapes passent par le même adaptateur que la trace du contrat. */
export function progressionUi(corps: ProgressionContrat): ProgressionTribunal {
  return {
    phase: estPhase(corps.phase) ? corps.phase : null,
    etapes: (corps.etapes ?? []).map(etapeTrace),
    activite: corps.activite ?? undefined,
  };
}

export interface OptionsSuivi {
  signal?: AbortSignal;
  /** Appelée à chaque relecture (et à chaque avis : Tribunal occupé, réseau). */
  onProgression?: (progression: ProgressionTribunal) => void;
  intervalleMs?: number;
  delaiMaxMs?: number;
  /** Remplacés dans les tests. */
  requete?: typeof fetch;
  attendre?: (ms: number, signal?: AbortSignal) => Promise<void>;
  maintenant?: () => number;
}

/**
 * Relit la progression d'un procès lancé en arrière-plan (`POST /progression`, #90) jusqu'à son
 * contrat. S3 seulement, jamais Bedrock. S'arrête au contrat, sur une erreur du procès (son motif),
 * après `delaiMaxMs`, ou quand `signal` est interrompu (l'utilisateur quitte l'écran).
 * Un 429 (Tribunal occupé) ou une coupure réseau ne sont pas des erreurs : la relecture continue.
 */
export async function suivreProces(urlApi: string, procesId: string, options: OptionsSuivi = {}): Promise<ContratTribunal> {
  const {
    signal, onProgression, intervalleMs = INTERVALLE_SUIVI_MS, delaiMaxMs = DELAI_MAX_SUIVI_MS,
    requete = fetch, attendre = attente, maintenant = Date.now,
  } = options;
  const debut = maintenant();
  let derniere: ProgressionTribunal = { phase: null, etapes: [] };
  const publier = (progression: ProgressionTribunal) => {
    derniere = progression;
    onProgression?.(progression);
  };

  for (;;) {
    let reponse: Response | null = null;
    try {
      reponse = await requete(`${urlApi}/progression`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id: procesId }),
        signal,
      });
    } catch (erreur) {
      if (signal?.aborted) throw erreur;
      publier({ ...derniere, avis: AVIS_RESEAU });
    }
    if (reponse?.status === 429) publier({ ...derniere, avis: AVIS_OCCUPE });
    else if (reponse && !reponse.ok) throw new Error(await lireErreur(reponse));
    else if (reponse) {
      const corps = (await reponse.json()) as ProgressionContrat;
      if (corps.statut === 'termine' && corps.contrat) return corps.contrat;
      if (corps.statut === 'erreur') throw new Error(corps.erreur ?? 'Le procès s’est arrêté sans motif.');
      const progression = progressionUi(corps);
      const lent = progression.phase === null && maintenant() - debut >= DELAI_DEMARRAGE_MS;
      publier(lent ? { ...progression, avis: AVIS_DEMARRAGE_LENT } : progression);
    }
    if (maintenant() - debut >= delaiMaxMs) {
      throw new Error(`Le procès n’a pas abouti en ${Math.round(delaiMaxMs / 1000)} s : suivi arrêté. Réessayez dans un instant.`);
    }
    await attendre(intervalleMs, signal);
  }
}

export interface OptionsJugement {
  signal?: AbortSignal;
  /**
   * Réponses du Pacte vécu (#68), quand il est terminé : en direct, la Lambda recalcule le seuil
   * en Python ; en démonstration, seul le procès tenu avec ces mêmes réponses (celles du profil
   * de test) peut être rejoué.
   */
  calibrage?: Record<string, string> | null;
  /** En direct, appelée à chaque relecture de la progression réelle (#90). */
  onProgression?: (progression: ProgressionTribunal) => void;
  /** En direct, appelée dès que la Lambda accepte le procès (202), avec son identifiant. */
  onAccepte?: (procesId: string) => void;
}

function contexteAdaptation(idProfil: string, decision: DecisionUI) {
  return { nomProfil: profilDe(idProfil)?.nom ?? idProfil, titreDecision: libelleDecision(decision) };
}

export async function jugerDecision(idProfil: string, decision: DecisionUI, options: OptionsJugement = {}): Promise<ResultatTribunal> {
  const { signal, calibrage, onProgression, onAccepte } = options;
  const contexte = contexteAdaptation(idProfil, decision);

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
    body: JSON.stringify({
      profil: idProfil,
      demande: demandeDecision(decision),
      progression: true,
      ...(calibrage ? { calibrage: { reponses: calibrage } } : {}),
    }),
    signal,
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  let procesId = reponse.headers.get('x-proces-id') ?? undefined;
  let contrat: ContratTribunal;
  if (reponse.status === 202) {
    procesId = ((await reponse.json()) as { id: string }).id;
    onAccepte?.(procesId);
    onProgression?.({ phase: null, etapes: [], activite: 'Procès accepté : les agents démarrent' });
    contrat = await suivreProces(URL_API, procesId, { signal, onProgression });
  } else {
    contrat = (await reponse.json()) as ContratTribunal; // Lambda d'avant #90 : le contrat arrive à la fin
  }
  return adapterContrat(contrat, { ...contexte, audience: numeroAudience(procesId), procesId });
}

/**
 * Reprend la relecture d'un procès en direct déjà accepté (#90) : l'utilisateur a quitté l'écran
 * ou rechargé la page pendant le procès, qui a continué sur la Lambda. Aucun nouveau procès.
 */
export async function reprendreProces(
  idProfil: string,
  decision: DecisionUI,
  procesId: string,
  options: Pick<OptionsJugement, 'signal' | 'onProgression'> = {},
): Promise<ResultatTribunal> {
  if (!URL_API) throw new Error('Adresse du Tribunal absente : définissez VITE_API_URL (Function URL de la Lambda).');
  const contrat = await suivreProces(URL_API, procesId, options);
  return adapterContrat(contrat, { ...contexteAdaptation(idProfil, decision), audience: numeroAudience(procesId), procesId });
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
 * Réveille la Lambda sans rien lui demander de coûteux : une vérification sans chiffre ni pièce
 * sur le procès affiché (une lecture S3, aucun appel Bedrock, réponse 200). Le premier vrai appel
 * évite ainsi le démarrage à froid (environ 4 s mesurées après un déploiement).
 */
export function reveillerLambda(procesId: string | undefined): void {
  if (!procesId || !greffierEnDirect(procesId)) return;
  fetch(`${URL_API}/verifier`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: procesId, texte: 'réveil', pieces: [] }),
  }).catch(() => { /* simple réveil : une erreur réseau sera signalée au vrai appel */ });
}

/** Question libre possible : mode direct (Bedrock payant, procès réarchivé) et procès archivé. */
export function questionLibreDisponible(procesId: string | undefined): boolean {
  return MODE_DIRECT && greffierEnDirect(procesId);
}

/**
 * Contre-interrogatoire (#55, `POST /question`) : l'orchestrateur choisit ses outils, le Procureur
 * et l'Avocat répondent avec les pièces, le Greffier vérifie les chiffres. Environ 20 à 40 s.
 */
export async function poserQuestion(procesId: string, question: string, signal?: AbortSignal): Promise<{ echange: EchangeContrat; pieces: PieceContrat[] }> {
  const reponse = await fetch(`${URL_API}/question`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: procesId, question }),
    signal,
  });
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  return (await reponse.json()) as { echange: EchangeContrat; pieces: PieceContrat[] };
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

/**
 * Ouvre le procès-verbal du procès dans un nouvel onglet (page imprimable, produite par Python).
 * La fenêtre est ouverte tout de suite, avant l'appel réseau, pour ne pas être bloquée
 * par le navigateur comme fenêtre surgissante.
 */
export async function ouvrirProcesVerbal(procesId: string | undefined): Promise<void> {
  if (!procesId) throw new Error('Ce procès n’a pas d’identifiant : il n’a pas été archivé.');
  if (!MODE_DIRECT) {
    window.open(`${import.meta.env.BASE_URL}proces-verbaux/${procesId}.html`, '_blank', 'noopener');
    return;
  }
  const fenetre = window.open('', '_blank');
  try {
    const reponse = await fetch(`${URL_API}/proces-verbal`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: procesId }),
    });
    if (!reponse.ok) throw new Error(await lireErreur(reponse));
    const page = new Blob([await reponse.text()], { type: 'text/html' });
    if (fenetre) fenetre.location.href = URL.createObjectURL(page);
  } catch (erreur) {
    fenetre?.close();
    throw erreur;
  }
}
