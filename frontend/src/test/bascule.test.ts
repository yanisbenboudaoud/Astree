/**
 * Points de bascule (#61) sur l'écran Verdict : lus dans le contrat, reliés aux règles du Pacte.
 */
import contratRobert from '../data/proces/2026-11-15-fcb6ce39f184.json';
import contratAmira from '../data/proces/2026-11-15-5ba5343b2165.json';
import contratRobertVecu from '../data/proces/2026-11-15-3da0fd68f5e4.json';
import contratMateo from '../data/proces/2026-11-15-c7c4bcc1736b.json';
import type { ContratTribunal, PointDeBasculeContrat } from '../api/contrat';
import { adapterContrat } from '../api/adaptateur';
import { pointsDeBascule } from '../domaine/verdict';

const POINT: PointDeBasculeContrat = {
  regle: 'pire_baisse_max',
  type: 'pire_baisse_max',
  seuil_actuel: -0.12,
  seuil_suffisant: -0.289679,
  taille_max: 0.09,
  message: "Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 %",
  pieces: ['P5'],
};

const adapter = (contrat: ContratTribunal) =>
  adapterContrat(contrat, { nomProfil: 'Robert', titreDecision: '30 % en TSLA', audience: '0142' });

describe('points de bascule', () => {
  it('procès enregistré avant #61 : aucun point, sans erreur', () => {
    const contrat = { ...(contratRobert as ContratTribunal) };
    delete contrat.points_de_bascule;
    expect(pointsDeBascule(adapter(contrat))).toEqual([]);
  });

  it('procès enregistrés : un point par règle calculable en violation, aucun pour une violation documentaire', () => {
    const regles = (contrat: unknown) => pointsDeBascule(adapter(contrat as ContratTribunal)).map((p) => p.regle);
    expect(regles(contratRobert)).toEqual(['pire_baisse_max']);
    expect(regles(contratAmira)).toEqual(['pire_baisse_max', 'plafond_crypto', 'pas_exclusivement_tech']);
    expect(regles(contratMateo)).toEqual([]);
  });

  it('Pacte vécu : le point de bascule suit le seuil mesuré', () => {
    const [classique] = pointsDeBascule(adapter(contratRobert as ContratTribunal));
    const [vecu] = pointsDeBascule(adapter(contratRobertVecu as ContratTribunal));
    expect(classique.message).toBe("Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 %");
    expect(vecu.message).toBe("Conforme jusqu'à 7 % en TSLA, ou avec un seuil de −29,0 % au lieu de −10,2 %");
  });

  it('un point par règle en violation, avec son paragraphe et son libellé du Pacte', () => {
    const contrat = { ...(contratRobert as ContratTribunal), points_de_bascule: [POINT] };
    expect(pointsDeBascule(adapter(contrat))).toEqual([{
      regle: 'pire_baisse_max',
      paragraphe: 1,
      libelle: 'Pire baisse tolérée : −12 %',
      message: POINT.message,
      pieces: ['P5'],
    }]);
  });
});
