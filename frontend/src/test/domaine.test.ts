/**
 * Adaptateur du contrat, questions du Greffier et options du Verdict, sur les vrais
 * procès enregistrés. Aucun nom de profil dans la logique : les tests vérifient qu'elle
 * lit le Pacte et le contrat.
 */
import contratRobert from '../data/proces/2026-11-15-fe7e9832703a.json';
import contratRobert25 from '../data/proces/2026-11-15-449f913437d8.json';
import contratMateo from '../data/proces/2026-11-15-d6b68c21715f.json';
import contratAmira from '../data/proces/2026-11-15-b6795c03a385.json';
import { pieges } from '../domaine/pieges';
import { jugerDecision, ProcesNonEnregistre } from '../api/tribunal';
import tsla from '../data/generated/decisions/robert/TSLA.json';
import xom from '../data/generated/decisions/mateo/XOM.json';
import type { ContratTribunal } from '../api/contrat';
import type { DecisionUI, TablePosition } from '../api/types';
import { adapterContrat, adapterEchange, etapeTrace, numeroAudience } from '../api/adaptateur';
import { profil } from '../api/donnees';
import { correspondAuContrat, demandeDecision, libelleDecision, messagesDecision } from '../domaine/decision';
import { questionsSuggerees, repondre } from '../domaine/questions';
import { optionsVerdict, archivage } from '../domaine/verdict';
import { MOINS, FINE } from '../lib/format';

const robert = profil('robert')!;
const mateo = profil('mateo')!;
const amira = profil('amira')!;
const decisionRobert: DecisionUI = { type: 'position', ticker: 'TSLA', taille: 30 };
const decisionMateo: DecisionUI = { type: 'position', ticker: 'XOM', taille: 10 };
const decisionAmira: DecisionUI = { type: 'panier', lignes: ['BTC-USD', 'ETH-USD', 'NVDA', 'QQQ'].map((ticker) => ({ ticker, poids: 25 })) };

const adapter = (contrat: unknown, nom: string, decision: DecisionUI) =>
  adapterContrat(contrat as ContratTribunal, { nomProfil: nom, titreDecision: libelleDecision(decision), audience: '0142' });

describe('décision', () => {
  it('libellé et demande envoyée au Tribunal', () => {
    expect(libelleDecision(decisionRobert)).toBe(`30${FINE}% en TSLA`);
    expect(demandeDecision(decisionRobert)).toBe('Je veux mettre 30 % de mon portefeuille en Tesla (TSLA)');
    expect(libelleDecision(decisionAmira)).toBe('Panier de 4 titres');
  });

  it('reconnaît la décision jugée par un procès enregistré', () => {
    expect(correspondAuContrat(decisionRobert, (contratRobert as ContratTribunal).decision)).toBe(true);
    expect(correspondAuContrat({ ...decisionRobert, taille: 15 }, (contratRobert as ContratTribunal).decision)).toBe(false);
    expect(correspondAuContrat(decisionAmira, (contratAmira as ContratTribunal).decision)).toBe(true);
  });

  it('message de violation avec correction vers le maximum conforme', () => {
    const table = tsla as TablePosition;
    const [message] = messagesDecision(robert, table.tailles[30], decisionRobert, table.maxConforme);
    expect(message.type).toBe('Violation');
    expect(message.titre).toBe('Cette taille enfreint votre Pacte (§1)');
    expect(message.correction).toEqual({ libelle: `Ramener à 9${FINE}%`, taille: 9 });
  });

  it('critère documentaire : la source ESG du dossier met XOM en conflit avec le Pacte', () => {
    const table = xom as TablePosition;
    const messages = messagesDecision(mateo, table.tailles[10], decisionMateo, table.maxConforme);
    expect(messages).toHaveLength(1);
    expect(messages[0].type).toBe('Violation');
    expect(messages[0].titre).toContain('Vos valeurs');
  });
});

describe('adaptateur du contrat', () => {
  const resultat = adapter(contratRobert, 'Robert', decisionRobert);

  it('arguments, pièces et contrôles triés par gravité', () => {
    expect(resultat.titre).toBe(`Robert c. « 30${FINE}% en TSLA »`);
    expect(resultat.arguments.filter((a) => a.camp === 'Procureur')).toHaveLength(4);
    expect(resultat.arguments.filter((a) => a.camp === 'Avocat')).toHaveLength(4);
    expect(resultat.controles[0].statut).toBe('Violation');
    expect(resultat.controles[0].paragraphe).toBe(1);
    expect(resultat.constat).toBe(`Pire baisse ${MOINS}29,0 % au-delà du seuil ${MOINS}12,0 % (Pacte §1).`);
  });

  it('chaque pièce sait quels arguments la citent', () => {
    for (const camp of ['Procureur', 'Avocat'] as const) {
      resultat.arguments.filter((a) => a.camp === camp).forEach((a, i) => {
        for (const code of a.pieces) {
          expect(resultat.pieces.find((p) => p.code === code)!.citeePar).toContain(`${camp} · argument ${i + 1}`);
        }
      });
    }
  });

  it('une correction du Greffier pendant le procès est gardée avec son motif', () => {
    expect(resultat.corrections.map((c) => c.motif)).toEqual([
      '« 16 866 » introuvable dans P3 : valeur négative, écrire le signe « − »',
      '« −12 % » introuvable dans P6 (présent dans P1, P4, P7, pièce non citée)',
    ]);
    const avecCorrection = adapter(contratRobert25, 'Robert', { type: 'position', ticker: 'TSLA', taille: 25 });
    expect(avecCorrection.corrections).toHaveLength(3);
    expect(avecCorrection.corrections[0].camp).toBe('Procureur');
    expect(avecCorrection.corrections[1].motif).toBe('« 30 % » introuvable dans P6');
    expect(avecCorrection.corrections[2].motif).toBe(
      '« 70,9 % » introuvable dans P1, P5 : valeur négative, écrire le signe « − »',
    );
    expect(avecCorrection.corrections[0].corrige).not.toBe(avecCorrection.corrections[0].original);
  });

  it('trace : raison de l’orchestrateur et pièce produite', () => {
    const appel = resultat.trace.find((e) => e.role === 'Orchestrateur')!;
    expect(appel.raison).toBeTruthy();
    expect(appel.sortie).toMatch(/^P\d+$/);
    expect(etapeTrace({ etape: 'avocat', outil: 'bedrock_correction' }).etat).toBe('signalement');
  });

  it('numéro d’audience tiré de l’identifiant S3', () => {
    expect(numeroAudience('2026-11-14-3f9a0c1b2d4e')).toBe(String(0x2d4e % 10000).padStart(4, '0'));
  });
});

describe('questions du Greffier', () => {
  const resultat = adapter(contratRobert, 'Robert', decisionRobert);
  const contexte = { profil: robert, resultat, decision: decisionRobert, table: tsla as TablePosition, pieces: resultat.pieces };

  it('propose « Et à 15 % ? », « Pourquoi pas 9 % ? » et la fiabilité', () => {
    expect(questionsSuggerees(contexte).map((q) => q.libelle)).toEqual([`Et à 15${FINE}% ?`, `Pourquoi pas 9${FINE}% ?`, 'Ces données sont-elles fiables ?']);
  });

  it('un nouveau calcul devient une nouvelle pièce, avec les chiffres de la table', () => {
    const reponse = repondre({ id: 'taille:15', libelle: 'Et à 15 % ?' }, contexte)!;
    expect(reponse.role).toBe('Greffier');
    expect(reponse.nouvellePiece?.code).toBe('G1');
    expect(reponse.texte).toContain(`${MOINS}16,4${FINE}%`);
    expect(reponse.texte).toContain(`${MOINS}13,4${FINE}%`);
  });

  it('panier : corrélation et part réallouable lues dans les pièces du procès', () => {
    const r = adapter(contratAmira, 'Amira', decisionAmira);
    const ctx = { profil: amira, resultat: r, decision: decisionAmira, table: null, pieces: r.pieces };
    const ids = questionsSuggerees(ctx).map((q) => q.id);
    expect(ids).toEqual(['correlation', 'part', 'fiabilite']);
    expect(repondre({ id: 'correlation', libelle: '' }, ctx)!.texte).toContain('0,84');
    expect(repondre({ id: 'part', libelle: '' }, ctx)!.texte).toContain(`28${FINE}%`);
  });
});

describe('options du Verdict', () => {
  it('position en violation : maintenir (avec engagement), ramener à 9 %, renoncer', () => {
    const resultat = adapter(contratRobert, 'Robert', decisionRobert);
    const table = tsla as TablePosition;
    const options = optionsVerdict({ profil: robert, resultat, decision: decisionRobert, table, entreeDecision: table.tailles[30] });
    expect(options.map((o) => o.id)).toEqual(['maintenir', 'ramener', 'renoncer']);
    expect(options[0].statut).toBe('Violation');
    expect(options[0].engagement).toContain(`${MOINS}29,0${FINE}%`);
    expect(options[1].titre).toBe(`Ramener la position à 9${FINE}%`);
    expect(options[1].mesures[0].valeur).toBe(`${MOINS}11,2${FINE}%`);
    expect(archivage(options[0], decisionRobert, 1).resume).toBe(`« 30${FINE}% en TSLA » maintenu malgré 1 violation · aucune transaction exécutée`);
  });

  it('violation documentaire seule : pas de taille à ramener', () => {
    const resultat = adapter(contratMateo, 'Mateo', decisionMateo);
    const options = optionsVerdict({ profil: mateo, resultat, decision: decisionMateo, table: xom as TablePosition, entreeDecision: null });
    expect(options.map((o) => o.id)).toEqual(['maintenir', 'renoncer']);
    expect(options[0].statut).toBe('Violation');
  });

  it('panier : la plus grande part réallouable vient du Tribunal (P4)', () => {
    const resultat = adapter(contratAmira, 'Amira', decisionAmira);
    const options = optionsVerdict({ profil: amira, resultat, decision: decisionAmira, table: null, entreeDecision: null });
    expect(options[1].titre).toBe(`Réallouer seulement 28${FINE}%`);
    expect(options[1].statut).toBe('Conforme');
  });
});

describe('contre-interrogatoire (#55)', () => {
  const contrat = contratRobert as ContratTribunal;
  // Pièce ajoutée par la question : numérotée à la suite du dossier enregistré.
  const nouvelle = `P${contrat.pieces.length + 1}`;
  const simulation15 = { ...contrat.pieces[1], id: nouvelle, titre: 'Simulation à 15 %', valeur_affichee: '−16,4 % max · +11,0 %/an' };
  const echange = {
    question: 'Et si je mettais 15 % au lieu de 30 % ?',
    pieces_ajoutees: [nouvelle],
    requisitoire: [{ etiquette: 'fait' as const, texte: 'À 15 %, la pire baisse simulée serait de −16,4 %.', pieces: ['P1', nouvelle] }],
    plaidoirie: [{ etiquette: 'fait' as const, texte: 'Le rendement annuel serait de +11,0 %.', pieces: [nouvelle] }],
    arguments_rejetes: [],
    controle_chiffres: { statut: 'conforme' as const, regle: 'verifier_chiffres', message: 'Chiffres cités vérifiés contre leurs pièces : 3/3 chiffres, 2 arguments' },
    trace: [{ etape: 'orchestrateur', outil: 'simuler_portefeuille', raison: 'Simuler la taille demandée.', entree: { taille: 0.15 }, sortie: nouvelle }],
  };

  it('adapte la réponse : arguments des deux camps, pièce ajoutée citée, contrôle du Greffier', () => {
    const resultat = adapterEchange(echange, [...contrat.pieces, simulation15]);
    expect(resultat.arguments.map((a) => a.camp)).toEqual(['Procureur', 'Avocat']);
    expect(resultat.piecesAjoutees.map((p) => p.code)).toEqual([nouvelle]);
    expect(resultat.piecesAjoutees[0].citeePar).toEqual(['Procureur · réponse 1', 'Avocat · réponse 1']);
    expect(resultat.controle).toContain('3/3 chiffres');
  });

  it('un procès relu avec ses questions archivées les affiche et les cite', () => {
    const avecQuestion = adapter({ ...contrat, pieces: [...contrat.pieces, simulation15], contre_interrogatoire: [echange] }, 'Robert', decisionRobert);
    expect(avecQuestion.echanges).toHaveLength(1);
    expect(avecQuestion.pieces.find((p) => p.code === nouvelle)!.citeePar).toContain('Procureur · question 1, réponse 1');
  });
});

describe('procès enregistrés (mode démonstration)', () => {
  it('rejoue le procès qui juge exactement la décision, avec son identifiant S3', async () => {
    const trente = await jugerDecision('robert', decisionRobert);
    expect(trente.procesId).toBe('2026-11-15-fe7e9832703a');
    const vingtCinq = await jugerDecision('robert', { type: 'position', ticker: 'TSLA', taille: 25 });
    expect(vingtCinq.procesId).toBe('2026-11-15-449f913437d8');
    expect(vingtCinq.audience).toBe(numeroAudience('2026-11-15-449f913437d8'));
  });

  it('sans procès pour cette décision, propose la décision de démonstration', async () => {
    await expect(jugerDecision('robert', { ...decisionRobert, taille: 12 })).rejects.toBeInstanceOf(ProcesNonEnregistre);
    try {
      await jugerDecision('robert', { ...decisionRobert, taille: 12 });
    } catch (e) {
      expect((e as ProcesNonEnregistre).decisionEnregistree).toEqual(decisionRobert);
    }
  });
});

describe('« Trompez le Greffier » : exemples prêts', () => {
  const exemples = pieges(adapter(contratRobert, 'Robert', decisionRobert));

  it('un vrai chiffre, un inventé, un arrondi faux et la mauvaise pièce, tous sur la pièce de simulation', () => {
    expect(exemples.map((e) => e.id)).toEqual(['vrai', 'invente', 'arrondi', 'piece']);
    expect(exemples.every((e) => e.pieces.join() === 'P2')).toBe(true);
    expect(exemples[0].texte).toContain(`${MOINS}29,0${FINE}%`);
    expect(exemples[1].texte).toContain(`${MOINS}40${FINE}%`);
    expect(exemples[2].texte).toContain(`${MOINS}28,9${FINE}%`);
    expect(exemples[3].texte).toContain(`${MOINS}23,7${FINE}%`);
  });

  it('aucun exemple sans pièce de simulation', () => {
    const sansSimulation = adapter({ ...(contratRobert as ContratTribunal), pieces: [] }, 'Robert', decisionRobert);
    expect(pieges(sansSimulation)).toEqual([]);
  });
});
