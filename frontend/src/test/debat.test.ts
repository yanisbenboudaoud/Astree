import { describe, expect, it } from 'vitest';
import type { ContratTribunal } from '../api/contrat';
import type { Argument } from '../api/types';
import { regrouperDebat, themeArgument } from '../domaine/debat';

const contrats = import.meta.glob<ContratTribunal>('../data/proces/2026-*.json', { eager: true, import: 'default' });

const argumentsDe = (contrat: ContratTribunal) => ({
  procureur: contrat.requisitoire.map((a): Argument => ({ camp: 'Procureur', texte: a.texte, provenance: 'Fait', pieces: a.pieces })),
  avocat: contrat.plaidoirie.map((a): Argument => ({ camp: 'Avocat', texte: a.texte, provenance: 'Fait', pieces: a.pieces })),
});

describe('thème d’un argument (première phrase)', () => {
  it.each([
    ['Au pire moment, votre portefeuille de 650 000 $ aurait perdu 188 291 $ avec cette position, contre 50 423 $ sans elle.', 'perte'],
    ['En 2022, avec 10 % en XOM, votre résultat aurait été de −3 819 $, contre −18 146 $ sans cette position.', 'annee_2022'],
    ['Avec 30 % en TSLA, le portefeuille a rendu +12,0 % par an, contre +9,3 % par an sans cette position.', 'rendement'],
    ['La règle « Pire baisse tolérée : −12 % » serait respectée jusqu’à 9 % en TSLA, avec une pire baisse de −11,2 %.', 'taille'],
    ['Une position de 9 % en TSLA respecte la règle « Pire baisse tolérée : −12 % », avec une pire baisse de −11,2 %.', 'taille'],
    ['Une position plus modeste respecte votre limite : à 9 % en TSLA, la pire baisse est de −11,2 %.', 'taille'],
    ['Une réallocation de 28 % du portefeuille respecte les trois règles du Pacte, au lieu des 100 % choisis.', 'taille'],
    ['Pris seul, XOM a connu une chute de 19,1 % depuis un sommet, au-delà de votre pire baisse tolérée de −15,1 %.', 'titre_seul'],
    ['Votre règle « Exclure les entreprises liées à des controverses » est en jeu : XOM fait l’objet d’une poursuite climatique.', 'valeurs'],
    ['Ce conflit s’est déjà présenté : 3 procès archivés portaient sur « 30 % en TSLA ».', 'antecedents'],
    ['Votre panier ne bouge pas d’un seul bloc : BTC-USD et NVDA ont évolué moins ensemble (0,32) que BTC-USD et ETH-USD (0,84).', 'diversification'],
    ['Parmi les titres comparés, TSLA a varié presque indépendamment de JNJ (−0,07) et de XBB.TO (0,08).', 'diversification'],
    ['Les frais annuels de gestion des FNB s’élèvent à 478 $ avec la décision, contre 682 $ sans cette position.', 'frais'],
    ['Les frais annuels du portefeuille réalloué coûtent 18 $ sur 40 000 $, contre 37 $ pour le portefeuille actuel.', 'frais'],
    ['Lors du rejeu d’une chute des cryptoactifs, vous avez répondu rester malgré une baisse de 73,7 %.', 'reactions'],
    ['Votre Pacte demande un « Équilibre entre croissance et stabilité ».', 'regles'],
    ['La règle « Crypto : exclue » est respectée : parmi les règles calculables, seule celle de pire baisse est en violation.', 'regles'],
  ])('%s → %s', (texte, theme) => {
    expect(themeArgument(texte)).toBe(theme);
  });

  it('seule la première phrase compte : la suite ne change pas le thème', () => {
    expect(themeArgument('Avec 10 % en TSLA, la plus forte chute atteint −18,7 %. Vous aviez choisi de rester à chacun des jours de marché revécus.'))
      .toBe('perte');
  });
});

describe('débat point par point sur les procès enregistrés', () => {
  it.each(Object.entries(contrats))('%s : chaque argument a un thème, rien ne se perd', (_, contrat) => {
    const { procureur, avocat } = argumentsDe(contrat);
    const points = regrouperDebat(procureur, avocat);
    expect(points.some((p) => p.theme === 'autre')).toBe(false);
    expect(points.flatMap((p) => p.procureur.map((a) => a.argument))).toHaveLength(procureur.length);
    expect(points.flatMap((p) => p.avocat.map((a) => a.argument))).toHaveLength(avocat.length);
  });

  it('les points suivent l’ordre du Procureur, et gardent le rang de chaque argument dans son camp', () => {
    const procureur: Argument[] = [
      { camp: 'Procureur', texte: 'Au pire moment, votre portefeuille aurait perdu 10 $.', provenance: 'Fait', pieces: ['P1'] },
      { camp: 'Procureur', texte: 'En 2022, le résultat aurait été de −5 $.', provenance: 'Fait', pieces: ['P2'] },
    ];
    const avocat: Argument[] = [
      { camp: 'Avocat', texte: 'Le portefeuille a gagné +12,0 % par an.', provenance: 'Fait', pieces: ['P1'] },
      { camp: 'Avocat', texte: 'Au pire moment, la perte reste dans la limite.', provenance: 'Fait', pieces: ['P1'] },
    ];
    const points = regrouperDebat(procureur, avocat);
    expect(points.map((p) => p.theme)).toEqual(['perte', 'annee_2022', 'rendement']);
    expect(points[0].avocat.map((a) => a.numero)).toEqual([2]);
    expect(points[1].avocat).toEqual([]);
  });
});
