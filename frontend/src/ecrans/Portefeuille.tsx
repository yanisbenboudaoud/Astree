/** Écran Portefeuille (annexe D.2), avec la recherche (D.3) et la confirmation après signature (C.6). */
import { useState, type CSSProperties } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import type { EntreeJournal, Profil, ReglePacte } from '../api/types';
import { configUi, donneesCalibrage, nomTitre, rechercheUi } from '../api/donnees';
import { Gabarit, useTitre } from '../components/Gabarit';
import { GraphiqueValeur } from '../components/graphiques/GraphiqueValeur';
import { Recherche } from '../components/Recherche';
import { Bouton } from '../components/Bouton';
import { Provenance } from '../components/Etiquettes';
import { Monogramme, Section } from '../components/Elements';
import { Icone } from '../components/Icone';
import { compte, date, dollars, jourMois, part, pourcent, seuil as seuilTexte } from '../lib/format';
import { bilanPacte, regleCle, seuilPireBaisse } from '../domaine/pacte';
import { regleMesuree } from '../domaine/calibrage';
import { useEtatProfil } from '../state/store';
import { InfoLimite, LimitesDonnees } from '../components/Limites';
import styles from './Portefeuille.module.css';

const TEINTES = ['var(--categorie-1)', 'var(--categorie-2)', 'var(--categorie-3)', 'var(--categorie-4)', 'var(--categorie-5)', 'var(--categorie-6)'];
const TEINTES_COURTES = ['var(--categorie-1)', 'var(--categorie-2)', 'var(--categorie-3)'];

/** Titres proposés en un clic sous la recherche : ceux de la décision de démonstration du profil, puis des exemples variés. */
const SUGGESTIONS_PAR_DEFAUT = ['TSLA', 'NVDA', 'XOM', 'BTC-USD'];
const NOMBRE_SUGGESTIONS = 5;

function suggestionsDe(profil: Profil): string[] {
  const demo = profil.decisionDemo;
  let tickers: string[] = [];
  if (demo?.type === 'position') tickers = [demo.ticker];
  else if (demo?.type === 'reallocation') tickers = demo.panier.map((l) => l.ticker);
  return [...new Set([...tickers, ...SUGGESTIONS_PAR_DEFAUT])].slice(0, NOMBRE_SUGGESTIONS);
}

/** Indicateurs compacts (#103) : libellé au-dessus, chiffre et contexte sur la même ligne. */
function Indicateurs({ profil }: { profil: Profil }) {
  const seuil = seuilPireBaisse(profil);
  return (
    <dl className={styles.indicateurs}>
      <div className={styles.indicateur}>
        <dt className={`t-petit-fort c-500 ${styles.libelleIndicateur}`}>Rendement annualisé <InfoLimite indicateur="rendement" libelle="Rendement annualisé" /></dt>
        <dd className={styles.valeurIndicateur}>
          <span className={styles.chiffreIndicateur}>{pourcent(profil.actuel.rendement, { signe: true })}</span>
        </dd>
      </div>
      <div className={styles.indicateur}>
        <dt className={`t-petit-fort c-500 ${styles.libelleIndicateur}`}>Chute maximale <InfoLimite indicateur="pire_baisse" libelle="Chute maximale" /></dt>
        <dd className={styles.valeurIndicateur}>
          <span className={styles.chiffreIndicateur}>{pourcent(profil.actuel.chuteMax)}</span>
          {seuil !== undefined && <span className="t-petit c-500">limite {seuilTexte(seuil)}</span>}
        </dd>
      </div>
      <div className={styles.indicateur}>
        <dt className={`t-petit-fort c-500 ${styles.libelleIndicateur}`}>Volatilité <InfoLimite indicateur="volatilite" libelle="Volatilité" /></dt>
        <dd className={styles.valeurIndicateur}>
          <span className={styles.chiffreIndicateur}>{pourcent(profil.actuel.volatilite)}</span>
        </dd>
      </div>
    </dl>
  );
}

/**
 * Positions regroupées par classe d'actifs (#105) : barre de répartition, puis un bloc par groupe
 * (sous-total en dollars et en part) et ses titres, chacun avec une barre de poids à l'échelle de la plus grosse ligne.
 * Survoler un groupe (barre, légende ou bloc) met ses lignes en avant ; l'information reste écrite, la couleur ne la porte jamais seule.
 */
function Positions({ profil }: { profil: Profil }) {
  const [survol, setSurvol] = useState<string | null>(null);
  const teintes = profil.groupes.length <= 3 ? TEINTES_COURTES : TEINTES;
  const teinte = (groupe: string) => teintes[profil.groupes.findIndex((g) => g.libelle === groupe) % teintes.length];
  const total = profil.positions.reduce((somme, p) => somme + p.valeur, 0);
  const poidsMax = Math.max(...profil.positions.map((p) => p.poids));
  const blocs = profil.groupes.map((g) => {
    const lignes = profil.positions.filter((p) => p.groupe === g.libelle).sort((a, b) => b.poids - a.poids);
    return { ...g, lignes, valeur: lignes.reduce((somme, p) => somme + p.valeur, 0) };
  });
  const couleur = (groupe: string) => ({ '--cat': teinte(groupe) }) as CSSProperties;
  const attenue = (groupe: string) => (survol !== null && survol !== groupe ? styles.attenue : '');
  const suivre = (groupe: string) => ({ onMouseEnter: () => setSurvol(groupe), onMouseLeave: () => setSurvol(null) });
  return (
    <Section
      id="titre-positions"
      titre="Vos positions"
      droite={(
        <span className={styles.groupeDroite}>
          <span className="t-petit c-500">{compte(profil.positions.length, 'titre')} · {dollars(total)}</span>
          <Provenance type="Fictif" />
        </span>
      )}
    >
      <div className={styles.repartition} aria-hidden="true">
        {blocs.map((g) => (
          <span key={g.libelle} className={attenue(g.libelle)} style={{ flexGrow: g.poids, ...couleur(g.libelle) }} {...suivre(g.libelle)} />
        ))}
      </div>
      <ul className={styles.legende} aria-label="Répartition par groupe">
        {blocs.map((g) => (
          <li key={g.libelle} className={attenue(g.libelle)} style={couleur(g.libelle)} {...suivre(g.libelle)}>
            <span className={styles.carre} aria-hidden="true" />
            <span className="t-petit c-700">{g.libelle}</span>
            <span className="t-tableau-fort">{part(g.poids)}</span>
          </li>
        ))}
      </ul>
      <div className={styles.tableauPositions} role="table" aria-label="Positions par groupe">
        <div className={`t-etiquette c-500 ${styles.colonnes}`} role="row">
          <span role="columnheader">Titre</span>
          <span role="columnheader" className={styles.colonnePoids}>Poids</span>
          <span role="columnheader" className={styles.montantLigne}>Valeur</span>
          <span role="columnheader" className={styles.poids}>Part</span>
        </div>
        {blocs.map((g) => (
          <div key={g.libelle} role="rowgroup" className={`${styles.groupe} ${attenue(g.libelle)}`} style={couleur(g.libelle)} {...suivre(g.libelle)}>
            <div className={styles.enteteGroupe} role="row">
              <span role="rowheader" className={styles.nomGroupe}>
                <span className={styles.carre} aria-hidden="true" />
                <span className="t-petit-fort">{g.libelle}</span>
                <span className="t-petit c-500">{compte(g.lignes.length, 'titre')}</span>
              </span>
              <span role="cell" className={styles.colonnePoids} />
              <span role="cell" className={`t-tableau-fort ${styles.montantLigne}`}>{dollars(g.valeur)}</span>
              <span role="cell" className={`t-tableau-fort ${styles.poids}`}>{part(g.poids)}</span>
            </div>
            {g.lignes.map((p) => (
              <div key={p.ticker} className={styles.ligne} role="row">
                <span role="cell" className={styles.titreLigne}>
                  <Monogramme ticker={p.ticker} className={styles.monoTeinte} />
                  <span className={styles.nom}>
                    <span className="t-corps">{nomTitre(p.ticker)}</span>
                    <span className="t-petit c-500">{p.ticker}</span>
                  </span>
                </span>
                <span role="cell" className={styles.colonnePoids}>
                  <span className={styles.barrePoids} aria-hidden="true"><span style={{ width: `${(p.poids / poidsMax) * 100}%` }} /></span>
                </span>
                <span role="cell" className={`t-tableau ${styles.montantLigne}`}>{dollars(p.valeur)}</span>
                <span role="cell" className={`t-tableau-fort ${styles.poids}`}>{part(p.poids)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Section>
  );
}

/** Ligne du bas de la carte du Pacte : la limite de pire baisse est-elle supposée ou mesurée (Pacte vécu, #68) ? */
function PacteVecu({ profil }: { profil: Profil }) {
  const mesuree = regleMesuree(profil);
  if (!donneesCalibrage(profil.id)) return null;
  return (
    <Link className={styles.pacteVecu} to={`/${profil.id}/pacte-vecu`}>
      <span className={styles.textePacteVecu}>
        <span className="t-petit-fort">{mesuree ? 'Limite mesurée' : 'Limite supposée'}</span>
        {mesuree && <span className="t-petit c-500">{mesuree.provenance}.</span>}
      </span>
      <span className={`t-petit-fort ${styles.actionPacteVecu}`}>
        {mesuree ? 'Revoir' : 'La mesurer'}
        <Icone nom="fleche-droite" taille={14} />
      </span>
    </Link>
  );
}

/** Le chiffre clé du Pacte : la valeur actuelle de la règle la plus proche de sa limite, et sa jauge. */
function RegleCle({ regle }: { regle: ReglePacte }) {
  const baisse = regle.type === 'pire_baisse_max';
  const limite = baisse ? regle.seuil : regle.max;
  const valeur = regle.valeur ?? 0;
  const utilisation = regle.utilisation ?? 0;
  const enViolation = regle.statut === 'violation';
  return (
    <div className={styles.regleCle}>
      <p className="t-petit c-500">{baisse ? 'Pire baisse observée' : regle.libelle}</p>
      <p className={styles.chiffreCle}>
        <span className={enViolation ? styles.chiffreViolation : undefined}>{baisse ? pourcent(valeur) : part(valeur)}</span>
        {limite !== undefined && <span className={styles.limiteCle}>/ {baisse ? seuilTexte(limite) : part(limite)}</span>}
      </p>
      <span
        className={`${styles.jaugePacte} ${enViolation ? styles.jaugeViolation : ''}`}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(utilisation * 100)}
        aria-label={`${regle.libelle} : ${pourcent(utilisation, { decimales: 0 })} de la limite utilisée`}
      >
        <span style={{ width: `${Math.min(1, Math.max(0, utilisation)) * 100}%` }} />
      </span>
    </div>
  );
}

const STATUT_REGLE: Record<ReglePacte['statut'], string> = { conforme: 'Respectée', violation: 'Enfreinte', a_verifier: 'À juger' };
const COULEUR_STATUT: Record<ReglePacte['statut'], string> = { conforme: styles.couleurConforme, violation: styles.couleurViolation, a_verifier: styles.couleurVerifier };

function CartePacte({ profil }: { profil: Profil }) {
  const cle = regleCle(profil);
  const bilan = bilanPacte(profil);
  const regles = profil.pacte.regles;
  return (
    <section className={styles.cartePacte} aria-labelledby="titre-pacte">
      <div className={styles.entetePacte}>
        <div className={styles.titrePacte}>
          <h2 className="t-panneau" id="titre-pacte">Votre Pacte</h2>
          <p className="t-petit c-500">Signé le {date(profil.pacte.dateSignature)}</p>
        </div>
        <span className={`t-petit-fort ${styles.etatPacte} ${bilan.violations ? styles.etatViolation : styles.etatConforme}`}>
          <span className={styles.point} aria-hidden="true" />
          {bilan.violations ? compte(bilan.violations, 'règle enfreinte', 'règles enfreintes') : 'Respecté'}
        </span>
      </div>
      {cle && <RegleCle regle={cle} />}
      <ol className={styles.regles} aria-label="Règles du Pacte">
        {regles.map((r, i) => (
          <li key={r.id}>
            <span className={`t-petit c-500 ${styles.numeroRegle}`}>§{i + 1}</span>
            <span className={styles.texteRegle}>
              <span className="t-petit">{r.libelle}</span>
              {r.provenance && <span className="t-petit c-500">{r.provenance}</span>}
            </span>
            <span className={`t-etiquette ${styles.statutRegle} ${COULEUR_STATUT[r.statut]}`}>{STATUT_REGLE[r.statut]}</span>
          </li>
        ))}
      </ol>
      <PacteVecu profil={profil} />
    </section>
  );
}

const LIBELLE_JOURNAL: Record<EntreeJournal['statut'], string> = {
  conforme: 'Conforme au Pacte',
  violation: 'En conflit avec le Pacte',
  a_verifier: 'À vérifier',
};

function Journal({ entrees }: { entrees: EntreeJournal[] }) {
  const [tout, setTout] = useState(false);
  const visibles = tout ? entrees : entrees.slice(0, 3);
  return (
    <section className={styles.journal} aria-labelledby="titre-journal">
      <div className={styles.enteteJournal}>
        <h2 className="t-panneau" id="titre-journal">Journal des décisions</h2>
        {entrees.length > 3 && (
          <Bouton variante="tertiaire" compact fleche={false} aria-expanded={tout} onClick={() => setTout((t) => !t)}>
            {tout ? 'Réduire' : 'Tout voir'}
          </Bouton>
        )}
      </div>
      <ol className={styles.frise}>
        {visibles.map((e) => (
          <li key={`${e.date}-${e.texte}`} className={`${styles.entree} ${COULEUR_STATUT[e.statut]} ${e.nouveau ? styles.entreeNouvelle : ''}`}>
            <span className={styles.point} aria-hidden="true" />
            <span className={styles.texteEntree}>
              <span className="t-corps">{e.texte}</span>
              <span className="visuellement-cache">{LIBELLE_JOURNAL[e.statut]}</span>
            </span>
            <time className="t-petit c-500" dateTime={e.date}>{jourMois(e.date)}</time>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Portefeuille({ profil }: { profil: Profil }) {
  useTitre('Portefeuille');
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const config = configUi(profil.id);
  const { etat, definirDecision, definirPanier, annulerSignature } = useEtatProfil(profil.id);
  const bilan = bilanPacte(profil);
  const archive = params.get('archive') === '1' && etat.archive;
  const journal = [...etat.journal, ...(config.journal ?? [])];
  const focusRecherche = Boolean((location.state as { recherche?: boolean } | null)?.recherche);
  // Tout profil peut tester un titre ou un panier ; le mode du profil (ou un panier entamé) n'est que le point de départ.
  const [modeRecherche, setModeRecherche] = useState(etat.panier.length > 0 ? 'panier' : config.recherche.mode);
  const recherche = rechercheUi(profil.id, modeRecherche);

  const instruire = (ticker: string) => {
    const defaut = profil.decisionDemo?.type === 'position' && profil.decisionDemo.ticker === ticker
      ? Math.round(profil.decisionDemo.taille * 100) : 10;
    const enCours = etat.decision?.type === 'position' && etat.decision.ticker === ticker ? etat.decision.taille : defaut;
    definirDecision({ type: 'position', ticker, taille: enCours });
    navigate(`/${profil.id}/decision`);
  };

  const instruirePanier = () => {
    const n = etat.panier.length;
    const base = Math.floor(100 / n / 5) * 5;
    const lignes = etat.panier.map((ticker, i) => ({ ticker, poids: i === 0 ? 100 - base * (n - 1) : base }));
    definirDecision({ type: 'panier', lignes });
    navigate(`/${profil.id}/decision`);
  };

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id}>
      <div className={styles.corps}>
        {archive && (
          <div className={styles.archive} role="status">
            <Icone nom="check" taille={18} />
            <div className={styles.texteArchive}>
              <p className="t-corps-fort">Verdict signé et archivé</p>
              <p className="t-petit">{etat.archive!.resume}</p>
            </div>
            <button
              type="button"
              className={styles.annulerSignature}
              onClick={() => {
                annulerSignature();
                params.delete('archive');
                setParams(params, { replace: true });
              }}
            >
              <Icone nom="annuler" taille={16} />
              Annuler la signature
            </button>
          </div>
        )}

        <div className={styles.titre}>
          <h1 className="t-h1">Bonjour {profil.nom}.</h1>
          {/* Seulement s'il y a un problème : la carte du Pacte dit déjà « Respecté ». */}
          {bilan.violations > 0 && (
            <p className={styles.statut}>
              <span className={styles.iconeViolation}><Icone nom="interdit" taille={18} /></span>
              <span className="t-corps c-700">Votre portefeuille enfreint {compte(bilan.violations, 'règle')} de votre Pacte.</span>
            </p>
          )}
        </div>

        <Recherche
          profil={profil}
          mode={recherche.mode}
          titre={recherche.titre}
          aide={recherche.aide}
          placeholder={recherche.placeholder}
          onMode={setModeRecherche}
          panier={etat.panier}
          onInstruire={instruire}
          onPanier={definirPanier}
          onInstruirePanier={instruirePanier}
          focusInitial={focusRecherche}
          suggestions={suggestionsDe(profil)}
        />

        <div className={styles.grille}>
          <div className={styles.principale}>
            <section className={`section ${styles.valeur}`} aria-labelledby="titre-valeur">
              <div className={styles.montant}>
                <div className={styles.blocValeur}>
                  <h2 className={`t-petit-fort c-500 ${styles.libelleIndicateur}`} id="titre-valeur">Valeur du portefeuille <InfoLimite indicateur="valeur" libelle="Valeur du portefeuille" /></h2>
                  <p className={styles.chiffre}>
                    <span className={styles.chiffreValeur}>{dollars(profil.capital)}</span>
                    <Provenance type="Fictif" />
                  </p>
                  <p className={styles.variation}>
                    <span className="t-tableau-fort">
                      <span aria-hidden="true">{profil.actuel.gain >= 0 ? '▲' : '▼'}</span>
                      <span className="visuellement-cache">{profil.actuel.gain >= 0 ? 'Hausse de ' : 'Baisse de '}</span>
                      {' '}{dollars(Math.abs(profil.actuel.gain))}
                    </span>
                    <span className="t-tableau">({pourcent(profil.actuel.gainPct, { signe: true })})</span>
                    <span className="t-petit c-500">depuis le {date(profil.debut)}</span>
                  </p>
                </div>
              </div>
              <GraphiqueValeur
                serie={profil.serieValeur}
                pointBas={{ date: profil.actuel.dateChuteMax, valeur: profil.actuel.valeurChuteMax, recul: profil.actuel.chuteMax }}
              />
              <Indicateurs profil={profil} />
              <p className={styles.provenance}>
                <Provenance type="Fait" />
                <span className="t-petit c-500">Prix réels du {date(profil.debut)} au {date(profil.fin)}, en CAD</span>
                <Provenance type="Fictif" />
                <span className="t-petit c-500">portefeuille de test</span>
              </p>
            </section>
            <Positions profil={profil} />
          </div>

          <aside className={styles.laterale} aria-label="Pacte et journal">
            <CartePacte profil={profil} />
            <Journal entrees={journal} />
            <LimitesDonnees ecran="portefeuille" variante="panneau" />
          </aside>
        </div>
      </div>
    </Gabarit>
  );
}
