import { FINE, MOINS, date, dollars, horizon, jourMois, moisAnnee, nombre, part, pourcent, tickerCourt } from '../lib/format';
import { normaliser, rechercherTitres } from '../lib/recherche';
import { TITRES } from '../api/donnees';

describe('formats français canadiens', () => {
  it('montants avec espace fine et symbole après', () => {
    expect(dollars(650000)).toBe(`650${FINE}000${FINE}$`);
  });

  it('pourcentages avec vrai signe moins et virgule décimale', () => {
    expect(pourcent(-0.077574)).toBe(`${MOINS}7,8${FINE}%`);
    expect(pourcent(0.119792, { signe: true })).toBe(`+12,0${FINE}%`);
    expect(pourcent(-0.12, { decimales: 0 })).toBe(`${MOINS}12${FINE}%`);
    expect(part(0.3)).toBe(`30${FINE}%`);
  });

  it('pas de « −0 » quand la valeur arrondie est nulle', () => {
    expect(nombre(-0.0004, 1)).toBe('0,0');
  });

  it('dates courtes', () => {
    expect(date('2026-11-12')).toBe('12 nov. 2026');
    expect(jourMois('2026-11-02')).toBe('02 nov.');
    expect(moisAnnee('2022-10-12')).toBe('oct. 2022');
  });

  it('horizon et ticker court', () => {
    expect(horizon([3, 5])).toBe('3 à 5 ans');
    expect(horizon([15, null])).toBe('15 ans et plus');
    expect(tickerCourt('XIU.TO')).toBe('XIU');
    expect(tickerCourt('BTC-USD')).toBe('BTC');
  });
});

describe('recherche (annexe D.3)', () => {
  it('ignore les accents et la casse', () => {
    expect(normaliser('Énergie Élevée')).toBe('energie elevee');
  });

  it('trouve par début de mot dans le nom, français ou d’origine', () => {
    expect(rechercherTitres(TITRES, 'tes').map((r) => r.titre.ticker)).toEqual(['TSLA']);
    expect(rechercherTitres(TITRES, 'royal').map((r) => r.titre.ticker)).toContain('RY.TO');
    expect(rechercherTitres(TITRES, 'canadien').map((r) => r.titre.ticker)).toContain('CNR.TO');
  });

  it('trouve par début de ticker et surligne la partie tapée', () => {
    const [premier] = rechercherTitres(TITRES, 'xo');
    expect(premier.titre.ticker).toBe('XOM');
    const ether = rechercherTitres(TITRES, 'eth')[0];
    expect(ether.titre.nom.slice(ether.surligne!.debut, ether.surligne!.debut + ether.surligne!.longueur)).toBe('Eth');
  });

  it('ne trouve pas au milieu d’un mot', () => {
    expect(rechercherTitres(TITRES, 'esla')).toEqual([]);
  });
});
