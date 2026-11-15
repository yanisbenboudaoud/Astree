import { describe, expect, it } from 'vitest';
import contratRobert from '../data/proces/2026-11-15-fe7e9832703a.json';
import contratMateo from '../data/proces/2026-11-15-d6b68c21715f.json';
import contratAmira from '../data/proces/2026-11-15-b6795c03a385.json';
import type { ContratTribunal } from '../api/contrat';
import { adapterContrat } from '../api/adaptateur';
import { bilanGreffier } from '../domaine/bilan';

const bilanDe = (contrat: unknown) => {
  const c = contrat as ContratTribunal;
  const resultat = adapterContrat(c, { nomProfil: 'Test', titreDecision: c.decision.libelle ?? '', audience: '0001' });
  return bilanGreffier(resultat.controles, c);
};

describe('bilan du Greffier en langage clair', () => {
  it('Robert, 30 % en TSLA : la règle enfreinte est dite en pourcentage et en dollars, tirés du contrat', () => {
    const bilan = bilanDe(contratRobert);
    expect(bilan.ton).toBe('violation');
    expect(bilan.verdict).toBe('1 règle de votre Pacte est enfreinte');
    // −29,0 % (comparaison du contrat), 188 291 $ sur 650 000 $ (pièce de simulation), limite de 12 %.
    expect(bilan.explication).toMatch(/perdrait 29,0\s%.*188\s291\s\$ sur 650\s000\s\$.*au plus 12\s%/);
  });

  it('Amira : plusieurs règles enfreintes, au pluriel', () => {
    const bilan = bilanDe(contratAmira);
    expect(bilan.verdict).toBe('3 règles de votre Pacte sont enfreintes');
  });

  it('Mateo : la controverse documentée est dite sans nom technique', () => {
    const bilan = bilanDe(contratMateo);
    expect(bilan.explication).toContain('Le dossier contient une source sur XOM');
    expect(bilan.controles.map((c) => `${c.titre} ${c.detail}`).join(' ')).not.toMatch(/controverse_esg_importante|_/);
  });

  it('chaque contrôle est rangé, et les contrôles du système parlent en clair', () => {
    const bilan = bilanDe(contratRobert);
    const total = bilan.comptes.enfreint + bilan.comptes.a_juger + bilan.comptes.verifie;
    expect(total).toBe((contratRobert as unknown as ContratTribunal).controles.length);
    const titres = bilan.controles.map((c) => c.titre);
    expect(titres).toContain('Aucun chiffre inventé');
    expect(titres).toContain('Aucun conseil, aucune promesse');
    // Le paragraphe du Pacte est dans le titre : la phrase ne le répète pas.
    expect(bilan.controles.some((c) => /Pacte §/.test(c.detail))).toBe(false);
  });
});
