import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import contratRobert from '../data/proces/2026-11-15-fcb6ce39f184.json';
import type { ContratTribunal } from '../api/contrat';
import type { Piece } from '../api/types';
import { adapterContrat } from '../api/adaptateur';
import { bilanGreffier } from '../domaine/bilan';
import { BULLETIN, epreuveDesDonnees, epreuveDuControle, type Bulletin, type Taux } from '../domaine/bulletin';
import { TiroirPiece } from '../components/TiroirPiece';
import { FINE } from '../lib/format';

// Lu comme dans l'application : sans fichier, le build et les autres tests passent.
const bulletinDuDepot = Object.values(import.meta.glob<Bulletin>('../data/bulletin.json', { eager: true, import: 'default' }))[0];

const taux = (k: number, n: number, valeur: number): Taux => ({ k, n, taux: valeur, rates: n - k, ic95: [0, 1] });

const bulletin = (pieges: Taux, legitimes: Taux, dansLeSeuil = taux(27, 27, 1)): Bulletin => ({
  depot: 'https://github.com/equipe/depot/blob/main/',
  mesures: {
    cadre_simulation: { issue: 166, rapport: 'docs/validation/evaluation_cadre.md', date: '2026-11-15', pieges, legitimes },
    validation_externe: {
      issue: 168, rapport: 'docs/validation/validation_externe.md', date: '2026-11-15', seuil_points: 0.25,
      fnb: ['XIU.TO', 'XBB.TO', 'ZST.TO', 'AGG', 'TLT', 'SPY', 'ESGV'], dans_le_seuil: dansLeSeuil, annee_2022: taux(7, 7, 1),
    },
  },
});

describe('bulletin du Greffier', () => {
  it('un taux sous 100 % est dit tel quel, avec le nombre de cas passés', () => {
    const epreuve = epreuveDuControle('cadre_simulation', bulletin(taux(47, 78, 0.6026), taux(71, 71, 1)));
    expect(epreuve?.texte).toBe(
      `Mis à l’épreuve : 47 conseils et promesses bloqués sur 78 (60${FINE}%) ; 31 sont passés sans être vus. `
      + '71 arguments légitimes admis sur 71. Mesure du 15 nov. 2026.');
    expect(epreuve?.complet).toBe(false);
    expect(epreuve?.lien).toBe('https://github.com/equipe/depot/blob/main/docs/validation/evaluation_cadre.md');
  });

  it('un argument légitime refusé à tort est dit aussi', () => {
    const epreuve = epreuveDuControle('cadre_simulation', bulletin(taux(78, 78, 1), taux(70, 71, 0.9859)));
    expect(epreuve?.texte).toContain('70 arguments légitimes admis sur 71 ; 1 refusé à tort.');
    expect(epreuve?.complet).toBe(false);
  });

  it('sans bulletin, ou pour un contrôle jamais mesuré, rien ne s’affiche', () => {
    expect(epreuveDuControle('cadre_simulation', null)).toBeNull();
    expect(epreuveDesDonnees(null)).toBeNull();
    expect(epreuveDuControle('verifier_chiffres', bulletin(taux(1, 1, 1), taux(1, 1, 1)))).toBeNull();
    expect(epreuveDuControle('biais_survivant')).toBeNull();
  });

  it('la validation externe : années dans le seuil, dont 2022, et les écarts au-delà sont annoncés', () => {
    expect(epreuveDesDonnees(bulletin(taux(1, 1, 1), taux(1, 1, 1)))?.texte).toBe(
      'Les prix de départ ont été confrontés aux rendements publiés par les émetteurs de 7 FNB : '
      + '27 années sur 27 à moins de 0,25 point d’écart, dont 2022 : 7 sur 7. Mesure du 15 nov. 2026.');
    const avecEcarts = epreuveDesDonnees(bulletin(taux(1, 1, 1), taux(1, 1, 1), taux(25, 27, 0.9259)));
    expect(avecEcarts?.texte).toContain('25 années sur 27 à moins de 0,25 point d’écart ; 2 au-delà, expliqués dans le rapport');
  });

  it.skipIf(!bulletinDuDepot)('le bulletin du dépôt est lu, et la phrase reprend exactement ses chiffres', () => {
    expect(BULLETIN).toEqual(bulletinDuDepot);
    for (const regle of ['verifier_chiffres', 'cadre_simulation'] as const) {
      const { pieges, legitimes } = bulletinDuDepot.mesures[regle]!;
      const texte = epreuveDuControle(regle)?.texte ?? '';
      expect(texte).toContain(` ${pieges.k} `);
      expect(texte).toContain(`sur ${pieges.n}`);
      expect(texte).toContain(`${legitimes.k} `);
      expect(texte).toContain(`admis sur ${legitimes.n}`);
    }
  });

  it.skipIf(!bulletinDuDepot)('le bilan du Greffier porte la mesure sous ses deux contrôles, pas sous les règles du Pacte', () => {
    const c = contratRobert as unknown as ContratTribunal;
    const resultat = adapterContrat(c, { nomProfil: 'Robert', titreDecision: '30 % en TSLA', audience: '0001' });
    const controles = bilanGreffier(resultat.controles, c).controles;
    const avecEpreuve = controles.filter((x) => x.epreuve).map((x) => x.regle).sort();
    expect(avecEpreuve).toEqual(['cadre_simulation', 'verifier_chiffres']);
    expect(controles.find((x) => x.regle === 'verifier_chiffres')?.epreuve?.lien).toMatch(/docs\/validation\/evaluation_chiffres\.md$/);
  });
});

describe('tiroir d’une pièce', () => {
  const piece = (outil: string): Piece => ({ code: 'P1', provenance: 'Fictif', titre: 'Simulation', valeur: '−29,0 %', outil });

  it.skipIf(!bulletinDuDepot)('une pièce de simulation dit que ses prix ont été vérifiés, avec le lien', () => {
    render(<TiroirPiece piece={piece('simuler_portefeuille')} onFermer={() => {}} />);
    expect(screen.getByRole('heading', { name: 'Données vérifiées' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Voir la mesure' })).toHaveAttribute('href', expect.stringMatching(/validation_externe\.md$/));
  });

  it('une autre pièce n’en dit rien', () => {
    render(<TiroirPiece piece={piece('calculer_correlations')} onFermer={() => {}} />);
    expect(screen.queryByRole('heading', { name: 'Données vérifiées' })).toBeNull();
  });
});
