/**
 * Annexe E, point 3 : les chiffres affichés, lus dans les tables générées par
 * scripts/build_ui_series.py, au dixième près.
 * Robert et le panier d'Amira reproduisent la spec ; pour Mateo, le portefeuille
 * du backend fait foi (personas/mateo.json), d'où −10,0 % et +13,5 % au lieu de
 * −10,3 % et +11,8 % (valeurs de la spec, calculées sur un autre portefeuille fictif).
 */
import robert from '../data/generated/profils/robert.json';
import tsla from '../data/generated/decisions/robert/TSLA.json';
import xom from '../data/generated/decisions/mateo/XOM.json';
import panierAmira from '../data/generated/paniers/amira.json';
import type { TablePanier, TablePosition } from '../api/types';

const enPoints = (v: number) => Math.round(v * 1000) / 10;

describe('Robert, portefeuille actuel', () => {
  it('rendement +9,3 %, volatilité 5,6 %, chute max −7,8 %, 2022 −2,6 %', () => {
    expect(enPoints(robert.actuel.rendement)).toBe(9.3);
    expect(enPoints(robert.actuel.volatilite)).toBe(5.6);
    expect(enPoints(robert.actuel.chuteMax)).toBe(-7.8);
    expect(enPoints(robert.actuel.rejeu2022)).toBe(-2.6);
  });

  it('valeur fictive, gain et point bas de la maquette', () => {
    expect(robert.capital).toBe(650000);
    expect(robert.actuel.gain).toBe(233034);
    expect(robert.actuel.valeurChuteMax).toBe(394058);
    expect(robert.actuel.dateChuteMax).toBe('2022-10-12');
  });
});

describe('Robert, position en TSLA', () => {
  const table = tsla as TablePosition;

  it('à 30 % : +12,0 %, 19,0 %, −29,0 %, −23,7 %', () => {
    const e = table.tailles[30];
    expect(enPoints(e.rendement)).toBe(12.0);
    expect(enPoints(e.volatilite)).toBe(19.0);
    expect(enPoints(e.chuteMax)).toBe(-29.0);
    expect(enPoints(e.rejeu2022)).toBe(-23.7);
  });

  it('à 9 % : chute max −11,2 %, et 9 % est le maximum conforme', () => {
    expect(enPoints(table.tailles[9].chuteMax)).toBe(-11.2);
    expect(table.maxConforme).toBe(9);
  });

  it('278 séances sous la limite à 30 %, du 23 févr. 2022 au 7 mai 2025', () => {
    expect(table.tailles[30].seances).toEqual({ nombre: 278, du: '2022-02-23', au: '2025-05-07' });
  });

  it('précalcule chaque pas de 1 point entre 0 et 50 %', () => {
    expect(table.tailles.map((t) => t.taille)).toEqual(Array.from({ length: 51 }, (_, i) => i));
  });
});

describe('Amira, panier crypto et tech', () => {
  const table = panierAmira as TablePanier;

  it('panier à 25 % chacun : chute max −58,5 %', () => {
    expect(enPoints(table.compositions['25-25-25-25'].chuteMax)).toBe(-58.5);
  });

  it('corrélation BTC/ETH : 0,84', () => {
    const paire = table.correlations.find((c) => c.a === 'BTC-USD' && c.b === 'ETH-USD');
    expect(Math.round(paire!.valeur * 100) / 100).toBe(0.84);
  });

  it('149 séances sous la limite de −45 %', () => {
    expect(table.compositions['25-25-25-25'].seances?.nombre).toBe(149);
  });
});

describe('Mateo, 10 % en XOM (portefeuille du backend)', () => {
  it('chute max −10,0 % et rendement +13,5 %, conformes au procès enregistré', () => {
    const e = (xom as TablePosition).tailles[10];
    expect(enPoints(e.chuteMax)).toBe(-10.0);
    expect(enPoints(e.rendement)).toBe(13.5);
  });
});
