import { describe, expect, it } from 'vitest';
import { accroche } from '../domaine/debat';
import { sansCoupure } from '../ecrans/Tribunal';

describe('accroche d’un argument (ligne repliée)', () => {
  it('coupe après la première phrase', () => {
    expect(accroche('Avec 10 % en TSLA, la pire baisse passe à −18,7 %. Elle reste sous le seuil.'))
      .toEqual({ tete: 'Avec 10 % en TSLA, la pire baisse passe à −18,7 %.', suite: 'Elle reste sous le seuil.' });
  });

  it('ne coupe ni sur une abréviation de mois ni sur un décimal', () => {
    const texte = 'Depuis le sommet du 27 déc. 2021, la valeur a baissé de −25,4 %.';
    expect(accroche(texte)).toEqual({ tete: texte, suite: '' });
  });

  it('coupe après une citation qui finit la phrase', () => {
    expect(accroche('Votre Pacte dit « Préserver mon capital ». TSLA a chuté.').suite).toBe('TSLA a chuté.');
  });
});

describe('montants sans coupure de ligne', () => {
  it('lie les milliers et l’unité au nombre', () => {
    expect(sansCoupure('perdu 188 291 $, soit −29,0 % en 2022'))
      .toBe('perdu 188\u202f291\u00a0$, soit −29,0\u00a0% en 2022');
  });
});
