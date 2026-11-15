import { describe, expect, it } from 'vitest';
import { decouperEnPoints, guidePiece, numeroPiece } from '../domaine/pieces';

describe('pièces à conviction expliquées', () => {
  it('coupe source, traitement et limites en points', () => {
    expect(decouperEnPoints('Une seule période de 5 ans ; biais du survivant ; le passé ne prédit pas l’avenir'))
      .toEqual(['Une seule période de 5 ans', 'Biais du survivant', 'Le passé ne prédit pas l’avenir']);
    expect(decouperEnPoints(undefined)).toEqual([]);
  });

  it('explique la pièce selon son outil, et le rejeu de 2022 à part', () => {
    expect(guidePiece({ outil: 'simuler_portefeuille', titre: 'Simulation du portefeuille avec 30 % en TSLA' })?.role)
      .toMatch(/5 dernières années/);
    expect(guidePiece({ outil: 'simuler_portefeuille', titre: 'Rejeu de 2022 avec 30 % en TSLA' })?.role).toMatch(/2022/);
    expect(guidePiece({ outil: 'charger_pacte', titre: 'Pacte d’Amira' })?.role).toMatch(/Pacte/);
  });

  it('retombe sur le type de la pièce pour un outil inconnu', () => {
    expect(guidePiece({ outil: 'outil_futur', type: 'declaree', titre: 'x' })?.role).toMatch(/investisseur/);
    expect(guidePiece({ titre: 'x' })).toBeNull();
  });

  it('numérote les pièces', () => {
    expect(numeroPiece('P12')).toBe(12);
    expect(numeroPiece('X')).toBeNull();
  });
});
