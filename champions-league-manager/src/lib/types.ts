export type Team = {
  id: string;
  name: string;
  /** Data URL of the crest (compressed client-side before storage). */
  logo?: string;
  /** 1-based entry order, used as the seeding reference for the pots. */
  seed: number;
  pot: number;
};

export type LeagueMatch = {
  id: string;
  matchday: number;
  /** Global reveal order across the whole league phase draw. */
  order: number;
  homeId: string;
  awayId: string;
  homeGoals: number | null;
  awayGoals: number | null;
  revealed: boolean;
};

export type KnockoutRoundId = "playoff" | "r16" | "qf" | "sf" | "final";

/** Where a slot's team comes from, so edits upstream propagate downstream. */
export type SlotSource = { type: "match"; matchId: string } | { type: "standing"; rank: number };

export type KnockoutMatch = {
  id: string;
  roundId: KnockoutRoundId;
  order: number;
  homeId: string | null;
  awayId: string | null;
  homeSource: SlotSource | null;
  awaySource: SlotSource | null;
  homeGoals: number | null;
  awayGoals: number | null;
  homePens: number | null;
  awayPens: number | null;
};

export type KnockoutRound = {
  id: KnockoutRoundId;
  name: string;
  teamCount: number;
  drawn: boolean;
  matches: KnockoutMatch[];
};

export type Awards = {
  mvp: string;
  topScorer: string;
  topAssister: string;
  /** Ajouté après coup : optionnel pour rester compatible avec l'existant. */
  topKeeper?: string;
};

export type LeaguePhase = {
  drawn: boolean;
  /** How many posters the user has already revealed during the draw. */
  revealed: number;
  matches: LeagueMatch[];
};

export type Tournament = {
  id: string;
  /** Identifiant public dans l'URL visiteur, attribué par le serveur. */
  slug?: string;
  /** Masqué volontairement par l'administrateur, même si l'étape 1 est finie. */
  hidden?: boolean;
  name: string;
  logo?: string;
  createdAt: number;
  updatedAt: number;
  teams: Team[];
  matchesPerTeam: number;
  potCount: number;
  league: LeaguePhase;
  /** Number of teams in the main knockout bracket (16, 8, 4...). */
  bracketSize: number;
  /** Ranking frozen when the user entered the knockout stage. */
  qualifiedSnapshot: string[] | null;
  knockout: KnockoutRound[];
  awards: Awards;
};

export type StandingRow = {
  teamId: string;
  rank: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  points: number;
  /** Last five results, most recent last. */
  form: Array<"W" | "D" | "L">;
};

export type QualificationBand = "direct" | "playoff" | "out";
