/**
 * Écran Décision (annexe D.4). Tout l'écran se recalcule quand la taille ou le panier
 * change, en lisant les tables précalculées par scripts/build_ui_series.py.
 */
import { useEffect, useId, useMemo, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import type { DecisionUI, EntreeSimulation, Profil, TablePanier, TablePosition } from '../api/types';
import { chargerTablePanier, chargerTablePosition, nomTitre, titre as titreDe } from '../api/donnees';
import { Gabarit, useTitre } from '../components/Gabarit';
import { Bouton } from '../components/Bouton';
import { Provenance, Statut } from '../components/Etiquettes';
import { LienRetour, Message, Monogramme, Section } from '../components/Elements';
import { Icone } from '../components/Icone';
import { GraphiqueRecul } from '../components/graphiques/GraphiqueRecul';
import { date, dollars, seuil as seuilTexte } from '../lib/format';
import { serieRecul } from '../lib/series';
import {
  effetsSurLePacte, entreePanier, entreePosition, ficheTitre, messagesDecision, totalPanier, type Effet,
} from '../domaine/decision';
import { seuilPireBaisse } from '../domaine/pacte';
import { tablePanierCalibree, tablePositionCalibree } from '../domaine/calibrage';
import { useEtatProfil } from '../state/store';
import styles from './Decision.module.css';

const RACCOURCIS_BASE = [5, 15, 30];

function raccourcis(maxConforme: number | null, tailleDefaut: number): number[] {
  const valeurs = new Set(RACCOURCIS_BASE);
  // Un maximum égal à 50 n'est que le bout du curseur : ce n'est pas une limite du Pacte.
  if (maxConforme !== null && maxConforme > 0 && maxConforme < 50) valeurs.add(maxConforme);
  valeurs.add(tailleDefaut);
  return [...valeurs].filter((v) => v > 0 && v <= 50).sort((a, b) => a - b).slice(0, 5);
}

/** Position d'une valeur sur le curseur, alignée sur le centre de la poignée (22 px). */
const position = (v: number) => `calc(11px + (100% - 22px) * ${v / 50})`;

function BlocTaille({ profil, decision, table, onTaille }: {
  profil: Profil;
  decision: Extract<DecisionUI, { type: 'position' }>;
  table: TablePosition;
  onTaille: (t: number) => void;
}) {
  const idCurseur = useId();
  const max = table.maxConforme;
  const horsLimite = max === null || decision.taille > max;
  const tailleDefaut = profil.decisionDemo?.type === 'position' && profil.decisionDemo.ticker === decision.ticker
    ? Math.round(profil.decisionDemo.taille * 100) : 10;
  const seuil = seuilPireBaisse(profil);
  const zones = useMemo(() => {
    const runs: { debut: number; fin: number; compatible: boolean }[] = [];
    table.tailles.forEach((e) => {
      const dernier = runs[runs.length - 1];
      if (dernier && dernier.compatible === e.compatible) dernier.fin = e.taille;
      else runs.push({ debut: e.taille, fin: e.taille, compatible: e.compatible });
    });
    return runs;
  }, [table]);

  return (
    <Section id="titre-taille" titre="Taille de la position">
      <div className={styles.valeurEtRaccourcis}>
        <div className={styles.valeurTaille}>
          <p className={`t-affiche ${horsLimite ? styles.horsLimite : ''}`} aria-live="polite">
            {decision.taille}{' '}%
            <span className="visuellement-cache">{horsLimite ? ', hors limite du Pacte' : ', compatible avec le Pacte'}</span>
          </p>
          <p className={styles.montantTaille}>
            <span className="t-petit c-700">≈ {dollars((decision.taille / 100) * profil.capital)} sur {dollars(profil.capital)}</span>
            <Provenance type="Fictif" />
          </p>
        </div>
        <div className={styles.raccourcis} role="group" aria-label="Tailles rapides">
          {raccourcis(max, tailleDefaut).map((v) => (
            <button key={v} type="button" className={styles.raccourci} aria-pressed={decision.taille === v} onClick={() => onTaille(v)}>
              {v === max && max < 50 && <Icone nom="check" taille={14} className={styles.iconeConforme} />}
              {v}{' '}%{v === max && max < 50 ? ' · max. conforme' : ''}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.curseur}>
        {max !== null && max < 50 && (
          <div className={styles.repereLimite} style={{ left: position(max) }} aria-hidden="true">
            <span className="t-petit-fort">Limite du Pacte · {max}{' '}%</span>
          </div>
        )}
        <div className={styles.piste} aria-hidden="true">
          <div className={styles.pisteRemplie} style={{ width: position(decision.taille) }} />
        </div>
        <label htmlFor={idCurseur} className="visuellement-cache">Taille de la position en {decision.ticker}, de 0 à 50 %</label>
        <input
          id={idCurseur}
          type="range"
          min={0}
          max={50}
          step={1}
          value={decision.taille}
          onChange={(e) => onTaille(Number(e.target.value))}
          aria-valuetext={`${decision.taille} %, ${horsLimite ? 'hors limite du Pacte' : 'compatible avec le Pacte'}`}
          className={styles.entreeCurseur}
        />
        <div className={styles.zones} aria-hidden="true">
          {zones.map((z, i) => {
            // Chaque zone commence là où la précédente finit (2 px d'écart), comme sur la maquette.
            const debut = i === 0 ? z.debut : zones[i - 1].fin;
            return (
              <span
                key={z.debut}
                className={z.compatible ? styles.zoneCompatible : styles.zoneHors}
                style={{ left: i === 0 ? position(debut) : `calc(${position(debut)} + 2px)`, width: `calc((100% - 22px) * ${(z.fin - debut) / 50} - ${i === 0 ? 0 : 2}px)` }}
              />
            );
          })}
        </div>
        <div className={styles.graduations} aria-hidden="true">
          {[0, 10, 20, 30, 40, 50].map((v) => <span key={v} style={{ left: position(v) }}>{v}{' '}%</span>)}
        </div>
      </div>

      <ul className={styles.legendeZones}>
        <li><span className={styles.carreCompatible} aria-hidden="true" />Compatible : {max === null ? 'aucune taille' : `0 à ${max} %`}</li>
        {(max === null || max < 50) && (
          <li>
            <span className={styles.carreHors} aria-hidden="true" />
            {seuil !== undefined ? `Au-delà, la chute observée dépasse ${seuilTexte(seuil)} ou une autre règle mesurable` : 'Au-delà, une règle mesurable du Pacte est enfreinte'}
          </li>
        )}
      </ul>

      <p className="t-petit c-500">Financement simulé : réduction proportionnelle de vos positions.</p>
    </Section>
  );
}

function BlocPanier({ decision, table, onLignes, onAjouter }: {
  decision: Extract<DecisionUI, { type: 'panier' }>;
  table: TablePanier | null;
  onLignes: (lignes: { ticker: string; poids: number }[]) => void;
  onAjouter: () => void;
}) {
  const total = totalPanier(decision);
  const pas = table?.pas ?? 5;
  const changer = (ticker: string, delta: number) => onLignes(decision.lignes.map((l) => (l.ticker === ticker ? { ...l, poids: Math.max(0, Math.min(100, l.poids + delta)) } : l)));
  return (
    <Section
      id="titre-composition"
      titre="Composition du panier"
      droite={(
        <p className={`t-petit ${total === 100 ? 'c-500' : styles.totalFaux}`} aria-live="polite">
          {total !== 100 && <Icone nom="interdit" taille={14} />}
          Total {total}{' '}%
        </p>
      )}
    >
      <ul className={styles.lignesPanier}>
        {decision.lignes.map((l) => {
          const t = titreDe(l.ticker);
          return (
            <li key={l.ticker} className={styles.lignePanier}>
              <Monogramme ticker={l.ticker} />
              <span className={styles.nomLigne}>
                <span className="t-corps">{nomTitre(l.ticker)}</span>
                <span className="t-petit c-500">{t?.secteur}</span>
              </span>
              <span className={styles.pasAPas} role="group" aria-label={`Poids de ${nomTitre(l.ticker)}`}>
                <button type="button" aria-label={`Diminuer ${nomTitre(l.ticker)} de ${pas} points`} disabled={l.poids <= 0} onClick={() => changer(l.ticker, -pas)}>
                  <Icone nom="moins" taille={14} />
                </button>
                <output className="t-tableau" aria-live="polite">{l.poids}{' '}%</output>
                <button type="button" aria-label={`Augmenter ${nomTitre(l.ticker)} de ${pas} points`} disabled={l.poids >= 100} onClick={() => changer(l.ticker, pas)}>
                  <Icone nom="plus" taille={14} />
                </button>
              </span>
              <button type="button" className={styles.retirerLigne} aria-label={`Retirer ${nomTitre(l.ticker)} du panier`} onClick={() => onLignes(decision.lignes.filter((x) => x.ticker !== l.ticker))}>
                <Icone nom="croix" taille={14} />
              </button>
            </li>
          );
        })}
      </ul>
      <Bouton variante="tertiaire" compact fleche={false} icone={<Icone nom="plus" taille={14} />} onClick={onAjouter} className={styles.ajouterTitre}>
        Ajouter un titre
      </Bouton>
      {total !== 100 && (
        <p id="erreur-total" className={`t-petit ${styles.totalFaux}`}>
          Le total fait {total}{' '}% : ajustez les poids pour atteindre 100{' '}%.
        </p>
      )}
    </Section>
  );
}

function CarteEffet({ effet }: { effet: Effet }) {
  const violation = effet.statut === 'Violation';
  return (
    <li className={`${styles.carteEffet} ${violation ? styles.carteViolation : ''}`}>
      <p className="t-petit-fort c-500">{effet.libelle}</p>
      <p className={styles.valeursEffet}>
        <span className="t-tableau c-500">{effet.avant}</span>
        <span className="t-corps c-500" aria-label="devient">→</span>
        <span className={`t-chiffre-moyen ${violation ? styles.horsLimite : ''}`}>{effet.apres}</span>
      </p>
      <p className={styles.limiteEffet}>
        <span className="t-petit c-500">{effet.limite}</span>
        {effet.statut && <Statut type={effet.statut} />}
      </p>
    </li>
  );
}

function BlocEffets({ profil, entree, decision, libelleGraphique }: { profil: Profil; entree: EntreeSimulation; decision: DecisionUI; libelleGraphique: string }) {
  const effets = effetsSurLePacte(profil, entree, decision);
  const actuel = useMemo(() => serieRecul(profil.actuel.recul, { date: profil.actuel.dateChuteMax, valeur: profil.actuel.chuteMax }), [profil]);
  const avec = useMemo(() => serieRecul(entree.recul, { date: entree.dateChuteMax, valeur: entree.chuteMax }), [entree]);
  return (
    <Section
      id="titre-effets"
      titre="Effet sur votre Pacte"
      droite={<p className="t-petit c-500">Sur la période du {date(profil.debut)} au {date(profil.fin)}</p>}
    >
      <ul className={styles.effets}>
        {effets.map((e) => <CarteEffet key={e.libelle} effet={e} />)}
      </ul>
      <GraphiqueRecul
        actuel={actuel}
        decision={avec}
        limite={seuilPireBaisse(profil)}
        creux={{ date: entree.dateChuteMax, valeur: entree.chuteMax }}
        seances={entree.seances}
        libelleDecision={libelleGraphique}
      />
      <p className={styles.provenance}>
        <Provenance type="Fait" />
        <span className="t-petit c-500">Rejeu sur les prix réels, en CAD. Le passé ne prédit pas l'avenir.</span>
      </p>
    </Section>
  );
}

export function Decision({ profil }: { profil: Profil }) {
  const navigate = useNavigate();
  const { etat, definirDecision, definirPanier } = useEtatProfil(profil.id);
  const decision = etat.decision;
  useTitre(decision?.type === 'panier' ? 'Composer un panier' : `Décision${decision?.type === 'position' ? ` · ${decision.ticker}` : ''}`);
  const [tablePosition, setTablePosition] = useState<TablePosition | null>(null);
  const [erreurTable, setErreurTable] = useState<string | null>(null);
  const [tablePanier, setTablePanier] = useState<TablePanier | null | undefined>(undefined);
  const idErreur = 'erreur-total';

  const ticker = decision?.type === 'position' ? decision.ticker : null;
  useEffect(() => {
    let actif = true;
    setErreurTable(null);
    // Profil créé (#86), en mode direct : la table est calculée par la Lambda et peut échouer.
    if (ticker) {
      chargerTablePosition(profil.id, ticker)
        .then((t) => actif && setTablePosition(t))
        .catch((e: Error) => actif && setErreurTable(e.message));
    }
    return () => { actif = false; };
  }, [profil.id, ticker]);
  useEffect(() => {
    let actif = true;
    if (decision?.type === 'panier') chargerTablePanier(profil.id).then((t) => actif && setTablePanier(t));
    return () => { actif = false; };
  }, [profil.id, decision?.type]);
  // Pacte vécu (#68) : statuts et taille maximale recalculés avec le seuil mesuré.
  const tablePositionMesuree = useMemo(() => tablePosition && tablePositionCalibree(tablePosition, profil), [tablePosition, profil]);
  const tablePanierMesuree = useMemo(() => tablePanier && tablePanierCalibree(tablePanier, profil), [tablePanier, profil]);

  if (!decision) return <Navigate to={`/${profil.id}/portefeuille`} replace />;

  let entree: EntreeSimulation | null = null;
  let maxConforme: number | null = null;
  if (decision.type === 'position' && tablePositionMesuree?.ticker === decision.ticker) {
    entree = entreePosition(tablePositionMesuree, decision.taille);
    maxConforme = tablePositionMesuree.maxConforme;
  }
  if (decision.type === 'panier' && tablePanierMesuree) entree = entreePanier(tablePanierMesuree, decision.lignes);
  const total = totalPanier(decision);
  const panierInvalide = decision.type === 'panier' && (total !== 100 || decision.lignes.length < 2);
  const messages = messagesDecision(profil, entree, decision, maxConforme);
  const nonPrecalcule = decision.type === 'panier' && tablePanier !== undefined && total === 100 && !entree;
  const chargement = decision.type === 'position' ? tablePosition?.ticker !== decision.ticker : tablePanier === undefined;

  const soumettre = () => {
    if (panierInvalide) return;
    navigate(`/${profil.id}/tribunal`);
  };

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="decision">
      <div className={styles.corps}>
        <LienRetour vers={`/${profil.id}/portefeuille`}>Portefeuille</LienRetour>
        <div className={styles.titre}>
          <p className="t-etiquette c-500">Instruction d'une décision</p>
          <h1 className="t-h1">
            {decision.type === 'position'
              ? `Quelle part de votre portefeuille en ${nomTitre(decision.ticker)} ?`
              : `Votre panier de ${decision.lignes.length} titre${decision.lignes.length > 1 ? 's' : ''}`}
          </h1>
          <p className={styles.fiche}>
            <Provenance type="Fait" />
            <span className="t-petit c-700">
              {decision.type === 'position'
                ? ficheTitre(decision.ticker, profil.debut, profil.fin)
                : `Remplace votre répartition actuelle · simulé sur ${Math.round((Date.parse(profil.fin) - Date.parse(profil.debut)) / 3.15576e10)} ans de prix réels`}
            </span>
          </p>
        </div>

        {decision.type === 'position' && tablePosition?.ticker === decision.ticker && (
          <BlocTaille profil={profil} decision={decision} table={tablePositionMesuree ?? tablePosition} onTaille={(t) => definirDecision({ ...decision, taille: t })} />
        )}
        {decision.type === 'panier' && (
          <BlocPanier
            decision={decision}
            table={tablePanierMesuree ?? null}
            onLignes={(lignes) => {
              definirDecision({ type: 'panier', lignes });
              definirPanier(lignes.map((l) => l.ticker));
            }}
            onAjouter={() => {
              definirPanier(decision.lignes.map((l) => l.ticker));
              navigate(`/${profil.id}/portefeuille`, { state: { recherche: true } });
            }}
          />
        )}

        {erreurTable
          ? <p className="t-corps c-700" role="alert">Simulation indisponible : {erreurTable}</p>
          : chargement && <p className="t-corps c-500" role="status">Chargement de la simulation…</p>}

        {entree && (
          <BlocEffets
            profil={profil}
            entree={entree}
            decision={decision}
            libelleGraphique={decision.type === 'position' ? `Avec ${decision.taille} % de ${decision.ticker}` : 'Avec le panier'}
          />
        )}

        {nonPrecalcule && tablePanier && (
          <Message type="À vérifier" titre="Simulation précalculée indisponible pour ce panier">
            Cette démonstration précalcule les paniers composés de {tablePanier.candidats.map(nomTitre).join(', ')}, par pas
            de {tablePanier.pas} points. Le Tribunal en direct simulera ce panier avec les mêmes outils.
          </Message>
        )}

        {messages.map((m) => (
          <Message
            key={m.titre}
            type={m.type}
            titre={m.titre}
            aide={m.aide}
            correction={m.correction && decision.type === 'position'
              ? { libelle: m.correction.libelle, onClick: () => definirDecision({ ...decision, taille: m.correction!.taille }) }
              : undefined}
          >
            <p>{m.corps}</p>
            {m.source && <p className="t-petit c-700">Source : {m.source}</p>}
          </Message>
        ))}

        <div className={styles.actions}>
          <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/portefeuille`}>Annuler</Bouton>
          <Bouton
            variante="primaire"
            onClick={soumettre}
            aria-disabled={panierInvalide || undefined}
            aria-describedby={panierInvalide ? idErreur : undefined}
          >
            Soumettre au Tribunal
          </Bouton>
        </div>
        {panierInvalide && decision.lignes.length < 2 && (
          <p id={idErreur} className="t-petit c-700">Un panier compte au moins deux titres.</p>
        )}
      </div>
    </Gabarit>
  );
}
