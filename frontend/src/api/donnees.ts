/**
 * Accès aux données précalculées (scripts/build_ui_series.py) et aux textes de démonstration.
 * Les tables de décision sont chargées à la demande : une par titre et par profil.
 */
import univers from '../data/generated/univers.json';
import libelles from '../data/libelles.json';
import profilsUi from '../data/profils_ui.json';
import type { ConfigProfilUI, Profil, TablePanier, TablePosition, Titre } from './types';

const profilsGeneres = import.meta.glob<Profil>('../data/generated/profils/*.json', { eager: true, import: 'default' });
const tablesPositions = import.meta.glob<TablePosition>('../data/generated/decisions/*/*.json', { import: 'default' });
const tablesPaniers = import.meta.glob<TablePanier>('../data/generated/paniers/*.json', { import: 'default' });

export const TITRES: Titre[] = univers as Titre[];
export const TITRES_PAR_TICKER: Record<string, Titre> = Object.fromEntries(TITRES.map((t) => [t.ticker, t]));
export const LIBELLES = libelles;

const PROFILS: Record<string, Profil> = Object.fromEntries(
  Object.values(profilsGeneres).map((p) => [p.id, p]),
);

export function idsProfils(): string[] {
  const ordre = profilsUi.ordre.filter((id) => id in PROFILS);
  const autres = Object.keys(PROFILS).filter((id) => !ordre.includes(id)).sort();
  return [...ordre, ...autres];
}

export function profil(id: string): Profil | undefined {
  return PROFILS[id];
}

const CONFIG_PAR_DEFAUT: Required<Pick<ConfigProfilUI, 'recherche'>> = {
  recherche: {
    mode: 'position',
    titre: 'Tester une décision',
    aide: "Simulez un achat, puis soumettez-le au Tribunal. Rien n'est acheté.",
    placeholder: 'Nom ou symbole, ex. : Apple ou AAPL',
  },
};

export function configUi(id: string): ConfigProfilUI & typeof CONFIG_PAR_DEFAUT {
  const config = (profilsUi.profils as Record<string, ConfigProfilUI>)[id] ?? {};
  return { ...CONFIG_PAR_DEFAUT, ...config } as ConfigProfilUI & typeof CONFIG_PAR_DEFAUT;
}

export function titre(ticker: string): Titre | undefined {
  return TITRES_PAR_TICKER[ticker];
}

export function nomTitre(ticker: string): string {
  return TITRES_PAR_TICKER[ticker]?.nom ?? ticker;
}

export async function chargerTablePosition(idProfil: string, ticker: string): Promise<TablePosition | null> {
  const chargeur = tablesPositions[`../data/generated/decisions/${idProfil}/${ticker}.json`];
  return chargeur ? chargeur() : null;
}

export async function chargerTablePanier(idProfil: string): Promise<TablePanier | null> {
  const chargeur = tablesPaniers[`../data/generated/paniers/${idProfil}.json`];
  return chargeur ? chargeur() : null;
}

export function libelleProfilRisque(code: string): string {
  return (libelles.profilsRisque as Record<string, string>)[code] ?? code;
}
