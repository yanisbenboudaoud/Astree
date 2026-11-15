/**
 * Sources du dossier (#111) : chaque source du contrat devient une ligne affichée, avec ses
 * pièces, la raison de l'orchestrateur et le libellé des règles qu'elle a permis de contrôler.
 */
import contratRobert from '../data/proces/2026-11-15-936f0f5659e5.json';
import type { ContratTribunal, SourceContrat } from '../api/contrat';
import { adapterContrat, adapterSource } from '../api/adaptateur';

const REGLES = [{ id: 'plafond_crypto', libelle: 'Crypto : exclue' }];

describe('sources du dossier (#111)', () => {
  it('garde les pièces, leurs raisons et le libellé des règles contrôlées', () => {
    const source: SourceContrat = {
      nom: "Univers d'actifs des organisateurs du datathon",
      fichier: 'assets_universe.csv',
      date_extraction: '2026-11-13',
      format: 'CSV',
      usage: 'La devise et la catégorie de chaque titre',
      pieces: [{ id: 'P2', raison: "Pièce obligatoire : mesurer la pire baisse." }, { id: 'P3' }],
      controles: ['plafond_crypto'],
    };
    expect(adapterSource(source, REGLES)).toEqual({
      nom: "Univers d'actifs des organisateurs du datathon",
      details: 'assets_universe.csv · CSV · extrait le 2026-11-13',
      usage: 'La devise et la catégorie de chaque titre',
      pieces: [{ code: 'P2', raison: 'Pièce obligatoire : mesurer la pire baisse.' }, { code: 'P3', raison: undefined }],
      regles: ['Crypto : exclue'],
    });
  });

  it("lit encore une source à l'ancien format, sans pièces ni usage", () => {
    const ancienne = { nom: 'Yahoo Finance via yfinance', fichier: 'prices_daily.csv', date_extraction: '2026-11-13' };
    expect(adapterSource(ancienne, REGLES)).toEqual({
      nom: 'Yahoo Finance via yfinance', details: 'prices_daily.csv · extrait le 2026-11-13', usage: undefined, pieces: [], regles: [],
    });
  });

  it('un procès enregistré passe ses sources à l’écran', () => {
    const resultat = adapterContrat(contratRobert as ContratTribunal, { nomProfil: 'Robert', titreDecision: '30 % en TSLA', audience: '0142' });
    expect(resultat.sources.map((s) => s.nom)).toEqual(contratRobert.sources.map((s) => s.nom));
  });
});

describe('affichage des sources (#111)', () => {
  it("n'écrit la raison d'une pièce qu'une fois, sous la première source qui l'utilise", async () => {
    const { sourcesAffichees } = await import('../domaine/sources');
    const raison = 'Mesurer la pire baisse.';
    const [prix, change] = sourcesAffichees([
      { nom: 'Prix', details: '', pieces: [{ code: 'P2', raison }, { code: 'P3' }], regles: [] },
      { nom: 'Change', details: '', pieces: [{ code: 'P2', raison }, { code: 'P4', raison: 'Autre.' }], regles: [] },
    ]);
    expect(prix.expliquees).toEqual([{ code: 'P2', raison }]);
    expect(prix.autres.map((p) => p.code)).toEqual(['P3']);
    expect(change.expliquees).toEqual([{ code: 'P4', raison: 'Autre.' }]);
    expect(change.autres.map((p) => p.code)).toEqual(['P2']);
  });
});
