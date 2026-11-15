/**
 * Formats français canadiens (spec, règles non négociables) :
 * espace insécable fine avant % et $, vrai signe moins (U+2212), dates « 12 nov. 2026 ».
 * Toutes les valeurs reçues sont des décimales brutes (0.30 = 30 %), comme dans le contrat.
 */

export const FINE = ' ';
export const MOINS = '−';

const cacheNombres = new Map<number, Intl.NumberFormat>();

function formateur(decimales: number): Intl.NumberFormat {
  let f = cacheNombres.get(decimales);
  if (!f) {
    f = new Intl.NumberFormat('fr-CA', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
    cacheNombres.set(decimales, f);
  }
  return f;
}

/** 650000 → « 650 000 » ; −0,5 → « −0,5 » (espaces fines, vrai signe moins). */
export function nombre(valeur: number, decimales = 0): string {
  const texte = formateur(decimales).format(Math.abs(valeur)).replace(/[\s  ]/g, FINE);
  const arrondi = Number(Math.abs(valeur).toFixed(decimales));
  return (valeur < 0 && arrondi !== 0 ? MOINS : '') + texte;
}

export interface OptionsPourcent {
  decimales?: number;
  /** Écrit le signe + devant une valeur positive. */
  signe?: boolean;
}

/** 0.0929 → « 9,3 % » ; avec signe → « +9,3 % » ; −0.2897 → « −29,0 % ». */
export function pourcent(ratio: number, { decimales = 1, signe = false }: OptionsPourcent = {}): string {
  const valeur = ratio * 100;
  const texte = nombre(valeur, decimales);
  const positif = Number(valeur.toFixed(decimales)) > 0;
  return `${signe && positif ? '+' : ''}${texte}${FINE}%`;
}

/** Seuil du Pacte : entier s'il est rond (−0.12 → « −12 % »), sinon au dixième (seuil mesuré −0.1016 → « −10,2 % »). */
export function seuil(ratio: number): string {
  return pourcent(ratio, { decimales: Number.isInteger(Math.round(ratio * 1e6) / 1e4) ? 0 : 1 });
}

/** Part d'un poids en points entiers : 0.3 → « 30 % ». */
export function part(ratio: number): string {
  return pourcent(ratio, { decimales: Number.isInteger(Math.round(ratio * 1000) / 10) ? 0 : 1 });
}

/** 650000 → « 650 000 $ ». */
export function dollars(valeur: number): string {
  return `${nombre(valeur)}${FINE}$`;
}

/** 650000 → « 650 k$ ». */
export function kiloDollars(valeur: number): string {
  return `${nombre(valeur / 1000)}${FINE}k$`;
}

/** Corrélation : 0.84453 → « 0,84 ». */
export function correlation(valeur: number): string {
  return nombre(valeur, 2);
}

function dateUtc(iso: string): Date {
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`);
}

const fDate = new Intl.DateTimeFormat('fr-CA', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const fJourMois = new Intl.DateTimeFormat('fr-CA', { day: '2-digit', month: 'short', timeZone: 'UTC' });
const fMoisAnnee = new Intl.DateTimeFormat('fr-CA', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const fMoisLong = new Intl.DateTimeFormat('fr-CA', { month: 'long', year: 'numeric', timeZone: 'UTC' });

const espaces = (texte: string) => texte.replace(/[  ]/g, ' ');

/** « 2026-11-12 » → « 12 nov. 2026 ». */
export function date(iso: string): string {
  return espaces(fDate.format(dateUtc(iso)));
}

/** « 2026-11-02 » → « 02 nov. » (journal). */
export function jourMois(iso: string): string {
  return espaces(fJourMois.format(dateUtc(iso)));
}

/** « 2022-10-12 » → « oct. 2022 ». */
export function moisAnnee(iso: string): string {
  return espaces(fMoisAnnee.format(dateUtc(iso)));
}

/** « 2022-02-23 » → « février 2022 ». */
export function moisLong(iso: string): string {
  return espaces(fMoisLong.format(dateUtc(iso)));
}

/** Horizon du profil : [3, 5] → « 3 à 5 ans » ; [15, null] → « 15 ans et plus ». */
export function horizon(bornes: [number, number | null] | number[]): string {
  const [min, max] = bornes;
  if (max === null || max === undefined) return `${min} ans et plus`;
  if (min === max) return `${min} ans`;
  return `${min} à ${max} ans`;
}

/** Ticker court du monogramme : sans « .TO » ni « -USD ». */
export function tickerCourt(ticker: string): string {
  return ticker.replace(/\.TO$/, '').replace(/-USD$/, '');
}

/** Pluriel simple : (2, 'règle') → « 2 règles ». */
export function compte(n: number, singulier: string, pluriel = `${singulier}s`): string {
  return `${n} ${n > 1 ? pluriel : singulier}`;
}
