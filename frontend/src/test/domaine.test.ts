/**
 * Adaptateur du contrat, questions du Greffier et options du Verdict, sur les vrais
 * procès enregistrés. Aucun nom de profil dans la logique : les tests vérifient qu'elle
 * lit le Pacte et le contrat.
 */
import contratRobert from '../data/proces/robert.json';
import contratMateo from '../data/proces/mateo.json';
import contratAmira from '../data/proces/amira.json';
import tsla from '../data/generated/decisions/robert/TSLA.json';
import xom from '../data/generated/decisions/mateo/XOM.json';
import type { ContratTribunal } from '../api/contrat';
import type { DecisionUI, TablePosition } from '../api/types';
import { adapterContrat, etapeTrace, numeroAudience } from '../api/adaptateur';
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
    const p5 = resultat.pieces.find((p) => p.code === 'P5')!;
    expect(p5.citeePar).toEqual(['Procureur · argument 2', 'Procureur · argument 3', 'Avocat · argument 2']);
    // Points de bascule (#61), cités des deux côtés.
    const bascule = resultat.pieces.find((p) => p.titre.startsWith('Ce qui changerait la réponse'))!;
    expect(bascule.citeePar).toEqual(['Procureur · argument 4', 'Avocat · argument 3']);
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
    expect(reponse.nouvellePiece?.code).toBe(`P${resultat.pieces.length + 1}`);
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
