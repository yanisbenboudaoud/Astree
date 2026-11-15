/**
 * Pouvoir d'achat (#113) : le rendement après inflation, calculé par Python
 * (pipeline/vues_interface.py) et lu dans les tables générées, sur l'écran Décision.
 */
import tsla from '../data/generated/decisions/robert/TSLA.json';
import type { DecisionUI, Profil, TablePosition } from '../api/types';
import { profil } from '../api/donnees';
import { effetsSurLePacte, entreePosition } from '../domaine/decision';
import { INDICATEURS } from '../domaine/limites';
import { FINE } from '../lib/format';

const robert = profil('robert')!;
const decision: DecisionUI = { type: 'position', ticker: 'TSLA', taille: 30 };
const entree = entreePosition(tsla as unknown as TablePosition, 30);
const ligneReelle = (p: Profil) => effetsSurLePacte(p, entree, decision).find((e) => e.indicateur === 'rendement_reel');

describe('rendement après inflation (#113)', () => {
  it('inflation du Canada de septembre 2021 à septembre 2026, dernier mois publié', () => {
    expect(robert.inflation).toMatchObject({ moisDebut: '2021-09', moisFin: '2026-09', publieLe: '2026-10-31' });
  });

  it('Robert, 30 % en TSLA : +5,5 % → +8,1 % par an après une inflation de 3,5 %/an', () => {
    expect(ligneReelle(robert)).toMatchObject({
      libelle: 'Rendement après inflation',
      detail: `inflation de 3,5${FINE}%/an`,
      avant: `+5,5${FINE}%`,
      apres: `+8,1${FINE}%`,
    });
  });

  it('la ligne suit le rendement en dollars et reste plus basse', () => {
    const effets = effetsSurLePacte(robert, entree, decision);
    const rang = effets.findIndex((e) => e.indicateur === 'rendement_reel');
    expect(effets[rang - 1].indicateur).toBe('rendement');
    expect(entree.rendementReel!).toBeLessThan(entree.rendement);
  });

  it('sans données macro (table plus ancienne ou fichier absent), pas de ligne', () => {
    expect(ligneReelle({ ...robert, inflation: null })).toBeUndefined();
    expect(ligneReelle({ ...robert, inflation: undefined, actuel: { ...robert.actuel, rendementReel: undefined } })).toBeUndefined();
  });

  it('la bulle ⓘ dit ce que mesure l’indicateur et sa limite', () => {
    expect(INDICATEURS.rendement_reel.mesure).toMatch(/pouvoir d’achat/);
    expect(INDICATEURS.rendement_reel.limite).toMatch(/dernier mois publié/);
  });
});
