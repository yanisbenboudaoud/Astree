/**
 * Pacte vécu (#68) : rejoue la dichotomie de pipeline/calibrage.py sur les jours de marché
 * précalculés, et applique le seuil mesuré au Pacte et aux tables de décision.
 *
 * Aucun chiffre n'est estimé ici : le seuil est la baisse réelle d'un jour précalculé par
 * Python, et les statuts sont la même comparaison que le Greffier (pire baisse < seuil →
 * violation). Le Tribunal recalcule tout en Python à partir des réponses.
 */
import type {
  DonneesCalibrage,
  EntreeSimulation,
  Profil,
  QuestionBaisse,
  QuestionCalibrage,
  ReglePacte,
  TablePanier,
  TablePosition,
} from '../api/types';
import { date as dateFr, pourcent } from '../lib/format';
import { estCalculable } from './pacte';

export const RESTE = 'reste';
export const VEND = 'vend';
const ID_REGLE_AJOUTEE = 'pire_baisse_mesuree';

export interface ReponsesCalibrage {
  reponses: Record<string, string>;
  /** Date ISO des dernières réponses (horodatage de la pièce « declaree »). */
  date: string;
}

export interface Parcours {
  poses: number[];
  reste: number;
  vend: number;
  prochain: number | null;
}

/** Même dichotomie que `parcours_dichotomie` (Python) : 4 questions au plus pour 10 niveaux. */
export function parcoursDichotomie(nombre: number, reponsesParRang: Record<number, string>): Parcours {
  let reste = -1;
  let vend = nombre;
  const poses: number[] = [];
  while (vend - reste > 1) {
    const milieu = Math.floor((reste + vend) / 2);
    const reponse = reponsesParRang[milieu];
    if (reponse === undefined) return { poses, reste, vend, prochain: milieu };
    poses.push(milieu);
    if (reponse === RESTE) reste = milieu;
    else vend = milieu;
  }
  return { poses, reste, vend, prochain: null };
}

function parRang(donnees: DonneesCalibrage, reponses: Record<string, string>): Record<number, string> {
  const resultat: Record<number, string> = {};
  donnees.episodes.forEach((e, rang) => {
    if (reponses[e.id] !== undefined) resultat[rang] = reponses[e.id];
  });
  return resultat;
}

/** Capacité (sur l'épisode le plus profond où l'utilisateur est resté), crypto, puis valeurs. */
export function questionsComplementaires(donnees: DonneesCalibrage, reste: number): QuestionCalibrage[] {
  const reference = donnees.episodes[Math.max(reste, 0)];
  const questions: QuestionCalibrage[] = [{
    id: 'capacite',
    type: 'capacite',
    choix: ['attendre', 'pas_attendre'],
    serie: reference.serie,
    date_sommet: reference.date_sommet,
    baisse: reference.baisse,
    annees_retour: reference.anneesRetour,
    horizon_ans: donnees.horizonAns,
  }];
  if (donnees.crypto) questions.push(donnees.crypto);
  return [...questions, ...donnees.valeurs];
}

export function prochaineQuestion(donnees: DonneesCalibrage, reponses: Record<string, string>): QuestionCalibrage | null {
  const { reste, prochain } = parcoursDichotomie(donnees.episodes.length, parRang(donnees, reponses));
  if (prochain !== null) return donnees.episodes[prochain];
  return questionsComplementaires(donnees, reste).find((q) => reponses[q.id] === undefined) ?? null;
}

export interface ResultatCalibrage {
  complet: boolean;
  /** Baisse réelle du dernier jour où l'utilisateur est resté ; null s'il a vendu dès le premier. */
  seuil: number | null;
  refusee: number | null;
  jours: { question: QuestionBaisse; reponse: string }[];
  /** Nombre maximal de jours de baisse qu'on peut lui montrer. */
  joursMax: number;
}

export function resultatCalibrage(donnees: DonneesCalibrage, reponses: Record<string, string>): ResultatCalibrage {
  const parcours = parcoursDichotomie(donnees.episodes.length, parRang(donnees, reponses));
  const complet = prochaineQuestion(donnees, reponses) === null;
  return {
    complet,
    seuil: parcours.prochain === null && parcours.reste >= 0 ? donnees.episodes[parcours.reste].baisse : null,
    refusee: parcours.prochain === null && parcours.vend < donnees.episodes.length ? donnees.episodes[parcours.vend].baisse : null,
    jours: parcours.poses.map((rang) => ({ question: donnees.episodes[rang], reponse: reponses[donnees.episodes[rang].id] })),
    joursMax: Math.ceil(Math.log2(donnees.episodes.length + 1)),
  };
}

// --- Le Pacte au seuil mesuré --------------------------------------------------------

export function regleMesuree(profil: Profil): ReglePacte | undefined {
  return profil.pacte.regles.find((r) => r.type === 'pire_baisse_max' && r.provenance);
}

/** Même texte que le Greffier (`controler_pire_baisse_max`) pour la pire baisse du portefeuille actuel. */
function jugerPireBaisse(chuteMax: number, seuil: number): Pick<ReglePacte, 'statut' | 'message'> {
  const texte = `Pire baisse ${pourcent(chuteMax, { signe: true })}`;
  return chuteMax < seuil
    ? { statut: 'violation', message: `${texte} au-delà du seuil ${pourcent(seuil, { signe: true })}` }
    : { statut: 'conforme', message: `${texte} dans la limite du seuil ${pourcent(seuil, { signe: true })}` };
}

/** Profil dont la règle de pire baisse porte le seuil mesuré (comme `appliquer_seuil` en Python). */
export function profilCalibre(profil: Profil, seuil: number, dateReponses: string): Profil {
  const existante = profil.pacte.regles.find((r) => r.type === 'pire_baisse_max');
  const regle: ReglePacte = {
    ...(existante ?? { id: ID_REGLE_AJOUTEE, type: 'pire_baisse_max' as const, valeur: null, utilisation: null, statut: 'conforme', message: '' }),
    seuil,
    libelle: `Pire baisse tolérée : ${pourcent(seuil, { signe: true })} (mesurée)`,
    provenance: `Mesurée sur vos réponses du ${dateFr(dateReponses)} à de vrais jours de marché`,
    valeur: profil.actuel.chuteMax,
    utilisation: profil.actuel.chuteMax / seuil,
    ...jugerPireBaisse(profil.actuel.chuteMax, seuil),
  };
  const regles = existante
    ? profil.pacte.regles.map((r) => (r.id === existante.id ? regle : r))
    : [regle, ...profil.pacte.regles];
  return { ...profil, pacte: { ...profil.pacte, regles } };
}

/** Le profil tel que l'utilisateur l'a calibré, ou tel quel si le Pacte vécu n'est pas terminé. */
export function profilAvecCalibrage(profil: Profil, donnees: DonneesCalibrage | undefined, calibrage: ReponsesCalibrage | null): Profil {
  if (!donnees || !calibrage) return profil;
  const resultat = resultatCalibrage(donnees, calibrage.reponses);
  return resultat.complet && resultat.seuil !== null ? profilCalibre(profil, resultat.seuil, calibrage.date) : profil;
}

// --- Les tables de décision au seuil mesuré -------------------------------------------

/**
 * Statut de la pire baisse recalculé avec le seuil mesuré. Les séances sous la limite,
 * comptées en Python avec l'ancien seuil, ne sont plus affichées (null).
 */
export function entreeCalibree<T extends EntreeSimulation>(entree: T, profil: Profil): T {
  const regle = regleMesuree(profil);
  if (!regle || regle.seuil === undefined) return entree;
  const statuts = { ...entree.statuts, [regle.id]: entree.chuteMax < regle.seuil ? 'violation' as const : 'conforme' as const };
  const compatible = profil.pacte.regles.filter(estCalculable).every((r) => statuts[r.id] === 'conforme');
  return { ...entree, statuts, compatible, seances: null };
}

export function tablePositionCalibree(table: TablePosition, profil: Profil): TablePosition {
  if (!regleMesuree(profil)) return table;
  const tailles = table.tailles.map((e) => entreeCalibree(e, profil));
  let maxConforme: number | null = null;
  for (const entree of tailles) {
    if (!entree.compatible) break;
    maxConforme = entree.taille;
  }
  return { ...table, tailles, maxConforme };
}

export function tablePanierCalibree(table: TablePanier, profil: Profil): TablePanier {
  if (!regleMesuree(profil)) return table;
  const compositions = Object.fromEntries(Object.entries(table.compositions).map(([cle, e]) => [cle, entreeCalibree(e, profil)]));
  return { ...table, compositions };
}
