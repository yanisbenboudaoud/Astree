/**
 * Pacte vécu (#68) : la dichotomie du navigateur donne le même seuil que Python
 * (pipeline/calibrage.py), et le seuil mesuré se répercute sur le Pacte et les tables.
 */
import tsla from '../data/generated/decisions/robert/TSLA.json';
import type { TablePosition } from '../api/types';
import { donneesCalibrage, profil } from '../api/donnees';
import {
  RESTE, VEND, parcoursDichotomie, prochaineQuestion, profilAvecCalibrage, resultatCalibrage, tablePositionCalibree,
} from '../domaine/calibrage';

const robert = profil('robert')!;
const donnees = donneesCalibrage('robert')!;

/** Un utilisateur qui reste tant que la baisse ne dépasse pas `limite`. */
function repondreJusqua(limite: number, autres: Record<string, string> = {}): Record<string, string> {
  const reponses: Record<string, string> = {};
  for (let question = prochaineQuestion(donnees, reponses); question; question = prochaineQuestion(donnees, reponses)) {
    if (question.type === 'baisse') reponses[question.id] = question.baisse >= limite ? RESTE : VEND;
    else reponses[question.id] = autres[question.type] ?? question.choix[0];
  }
  return reponses;
}

describe('Pacte vécu', () => {
  it('dichotomie : 4 questions au plus pour 10 niveaux', () => {
    for (let limite = -1; limite < 10; limite += 1) {
      const reponses = Object.fromEntries(Array.from({ length: 10 }, (_, rang) => [rang, rang <= limite ? RESTE : VEND]));
      const { poses, reste, vend, prochain } = parcoursDichotomie(10, reponses);
      expect(prochain).toBeNull();
      expect(poses.length).toBeLessThanOrEqual(4);
      expect([reste, vend]).toEqual([limite, limite + 1]);
    }
  });

  it('les réponses de démonstration donnent le seuil calculé en Python', () => {
    for (const id of ['robert', 'amira', 'mateo']) {
      const d = donneesCalibrage(id)!;
      const resultat = resultatCalibrage(d, d.demo!.reponses);
      expect(resultat.complet).toBe(true);
      expect(resultat.seuil).toBe(d.demo!.seuil);
    }
  });

  it('aucune donnée après le jour de la question', () => {
    for (const episode of donnees.episodes) {
      expect(episode.historique[episode.historique.length - 1][0]).toBe(episode.date_jour);
    }
  });

  it('le Pacte prend le seuil mesuré, avec sa provenance', () => {
    const reponses = repondreJusqua(-0.12);
    const calibre = profilAvecCalibrage(robert, donnees, { reponses, date: '2026-11-15' });
    const regle = calibre.pacte.regles.find((r) => r.type === 'pire_baisse_max')!;
    expect(regle.seuil).toBe(resultatCalibrage(donnees, reponses).seuil);
    expect(regle.provenance).toMatch(/15 nov\. 2026/);
    expect(regle.statut).toBe('conforme'); // le portefeuille actuel (−7,8 %) reste dans la limite
  });

  it('sans réponse complète, le Pacte ne change pas', () => {
    const { capacite: _, ...incompletes } = repondreJusqua(-0.12);
    expect(profilAvecCalibrage(robert, donnees, { reponses: incompletes, date: '2026-11-15' })).toBe(robert);
    expect(profilAvecCalibrage(robert, donnees, null)).toBe(robert);
  });

  it('la taille maximale compatible suit le seuil mesuré', () => {
    const table = tsla as TablePosition;
    const strict = profilAvecCalibrage(robert, donnees, { reponses: repondreJusqua(-0.08), date: '2026-11-15' });
    const large = profilAvecCalibrage(robert, donnees, { reponses: repondreJusqua(-0.32), date: '2026-11-15' });
    const maxLarge = tablePositionCalibree(table, large).maxConforme!;
    // −5,4 % mesuré : le portefeuille actuel (−7,8 %) le dépasse déjà, aucune taille n'est compatible.
    expect(tablePositionCalibree(table, strict).maxConforme).toBeNull();
    expect(maxLarge).toBeGreaterThan(table.maxConforme!);
    const seuilLarge = large.pacte.regles.find((r) => r.type === 'pire_baisse_max')!.seuil!;
    expect(tablePositionCalibree(table, large).tailles[30].statuts.pire_baisse_max).toBe(table.tailles[30].chuteMax < seuilLarge ? 'violation' : 'conforme');
  });
});
