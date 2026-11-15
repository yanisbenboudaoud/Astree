/**
 * Accès aux données précalculées (scripts/build_ui_series.py) et aux textes de démonstration.
 * Les tables de décision sont chargées à la demande : une par titre et par profil.
 *
 * Profils créés par le questionnaire (#86) : la Lambda renvoie à la signature leurs vues
 * (mêmes formats que les fichiers précalculés, `pipeline/vues_interface.py`), gardées ici et
 * dans sessionStorage ; en mode direct, leurs tables de décision viennent de `POST /table`.
 */
import univers from '../data/generated/univers.json';
import libelles from '../data/libelles.json';
import profilsUi from '../data/profils_ui.json';
import { MODE_DIRECT, URL_API, lireErreur } from './config';
import type { ConfigProfilUI, ConfigRecherche, DonneesCalibrage, Profil, TablePanier, TablePosition, Titre } from './types';

const profilsGeneres = import.meta.glob<Profil>('../data/generated/profils/*.json', { eager: true, import: 'default' });
const tablesPositions = import.meta.glob<TablePosition>('../data/generated/decisions/*/*.json', { import: 'default' });
const tablesPaniers = import.meta.glob<TablePanier>('../data/generated/paniers/*.json', { import: 'default' });
const calibrages = import.meta.glob<DonneesCalibrage>('../data/generated/calibrage/*.json', { eager: true, import: 'default' });

export const TITRES: Titre[] = univers as Titre[];
export const TITRES_PAR_TICKER: Record<string, Titre> = Object.fromEntries(TITRES.map((t) => [t.ticker, t]));
export const LIBELLES = libelles;

const PROFILS: Record<string, Profil> = Object.fromEntries(
  Object.values(profilsGeneres).map((p) => [p.id, p]),
);

/** Ce que l'interface lit pour un profil créé : écran Portefeuille et « Revivez 4 jours ». */
export interface VuesProfil {
  profil: Profil;
  calibrage: DonneesCalibrage;
}

const CLE_PROFILS_CREES = 'astree.profils.v1';

function lireProfilsCrees(): Record<string, VuesProfil> {
  try {
    const brut = sessionStorage.getItem(CLE_PROFILS_CREES);
    return brut ? (JSON.parse(brut) as Record<string, VuesProfil>) : {};
  } catch {
    return {};
  }
}

const PROFILS_CREES: Record<string, VuesProfil> = lireProfilsCrees();

/** Garde les vues d'un profil signé : tous les écrans le trouvent ensuite par son identifiant. */
export function enregistrerProfilCree(vues: VuesProfil): void {
  PROFILS_CREES[vues.profil.id] = vues;
  try {
    sessionStorage.setItem(CLE_PROFILS_CREES, JSON.stringify(PROFILS_CREES));
  } catch {
    /* stockage indisponible : le profil reste en mémoire jusqu'au rechargement */
  }
}

/** Profils créés pendant cette session, le plus récent d'abord. */
export function profilsCrees(): Profil[] {
  return Object.values(PROFILS_CREES).map((v) => v.profil).reverse();
}

export function idsProfils(): string[] {
  const ordre = profilsUi.ordre.filter((id) => id in PROFILS);
  const autres = Object.keys(PROFILS).filter((id) => !ordre.includes(id)).sort();
  return [...ordre, ...autres];
}

export function profil(id: string): Profil | undefined {
  return PROFILS[id] ?? PROFILS_CREES[id]?.profil;
}

const CONFIG_PAR_DEFAUT: Required<Pick<ConfigProfilUI, 'recherche'>> = {
  recherche: {
    mode: 'position',
    titre: 'Quelle décision voulez-vous tester ?',
    aide: "Simulez un achat, puis soumettez-le au Tribunal. Rien n'est acheté.",
    placeholder: 'Nom ou symbole, ex. : Apple ou AAPL',
  },
};

const RECHERCHE_PANIER_PAR_DEFAUT: ConfigRecherche = {
  mode: 'panier',
  titre: 'Quel panier voulez-vous tester ?',
  aide: "Ajoutez plusieurs titres : le Tribunal juge le panier en entier. Rien n'est acheté.",
  placeholder: 'Nom ou symbole, ex. : Apple ou AAPL',
};

export function configUi(id: string): ConfigProfilUI & typeof CONFIG_PAR_DEFAUT {
  const config = (profilsUi.profils as Record<string, ConfigProfilUI>)[id] ?? {};
  return { ...CONFIG_PAR_DEFAUT, ...config } as ConfigProfilUI & typeof CONFIG_PAR_DEFAUT;
}

/** Textes de la recherche pour un mode : ceux du profil s'il a choisi ce mode, sinon les textes génériques. */
export function rechercheUi(id: string, mode: ConfigRecherche['mode']): ConfigRecherche {
  const { recherche } = configUi(id);
  if (recherche.mode === mode) return recherche;
  return mode === 'panier' ? RECHERCHE_PANIER_PAR_DEFAUT : CONFIG_PAR_DEFAUT.recherche;
}

export function titre(ticker: string): Titre | undefined {
  return TITRES_PAR_TICKER[ticker];
}

export function nomTitre(ticker: string): string {
  return TITRES_PAR_TICKER[ticker]?.nom ?? ticker;
}

const tablesCalculees = new Map<string, Promise<TablePosition>>();

export async function chargerTablePosition(idProfil: string, ticker: string): Promise<TablePosition | null> {
  const chargeur = tablesPositions[`../data/generated/decisions/${idProfil}/${ticker}.json`];
  if (chargeur) return chargeur();
  if (!MODE_DIRECT || !URL_API || !(idProfil in PROFILS_CREES)) return null;
  const cle = `${idProfil}/${ticker}`;
  let table = tablesCalculees.get(cle);
  if (!table) {
    // Calculée par Python sur la Lambda, sans Bedrock (route /table, #86).
    table = fetch(`${URL_API}/table`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ profil: idProfil, ticker }),
    }).then(async (reponse) => {
      if (!reponse.ok) throw new Error(await lireErreur(reponse));
      return (await reponse.json()) as TablePosition;
    });
    table.catch(() => tablesCalculees.delete(cle));
    tablesCalculees.set(cle, table);
  }
  return table;
}

export async function chargerTablePanier(idProfil: string): Promise<TablePanier | null> {
  const chargeur = tablesPaniers[`../data/generated/paniers/${idProfil}.json`];
  return chargeur ? chargeur() : null;
}

/** Jours de marché du Pacte vécu (#68) pour ce profil, ou undefined s'ils n'ont pas été générés. */
export function donneesCalibrage(idProfil: string): DonneesCalibrage | undefined {
  return calibrages[`../data/generated/calibrage/${idProfil}.json`] ?? PROFILS_CREES[idProfil]?.calibrage;
}

export function libelleProfilRisque(code: string): string {
  return (libelles.profilsRisque as Record<string, string>)[code] ?? code;
}
