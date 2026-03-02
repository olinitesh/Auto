import { useMemo, useState } from "react";

import "./comparison.css";

type VehicleTarget = {
  make: string;
  model: string;
  year: number;
  trim?: string;
};

type DealerSiteInput = {
  dealer_id: string;
  dealer_name: string;
  dealer_zip: string;
  brand: string;
  site_url: string;
  inventory_url: string;
  adapter_key: string;
};

type DealerOffer = {
  offer_id: string;
  dealership_id: string;
  dealership_name: string;
  distance_miles: number;
  vehicle_id: string;
  vehicle_label: string;
  otd_price: number;
  fees: number;
  market_adjustment: number;
  specs_score: number;
  data_provider?: string;
  days_on_market?: number;
  days_on_market_source?: string;
  days_on_market_bucket?: string;
  price_drop_7d?: number;
  price_drop_30d?: number;
  inventory_status?: string;
  is_in_transit?: boolean;
  is_pre_sold?: boolean;
  is_hidden?: boolean;
  listing_url?: string;
  dealer_url?: string;
};

type RankedOffer = {
  rank: number;
  offer: DealerOffer;
  score: number;
  score_breakdown: Record<string, number>;
};

type OfferHistoryPoint = {
  otd_price: number;
  seen_at: string;
  data_provider?: string;
};

type OfferHistoryResponse = {
  dealership_id: string;
  vehicle_id: string;
  first_seen_at?: string;
  last_seen_at?: string;
  days_on_market?: number;
  points: OfferHistoryPoint[];
};

type OfferTrendKey = {
  dealership_id: string;
  vehicle_id: string;
};

type OfferTrendItem = {
  dealership_id: string;
  vehicle_id: string;
  first_seen_at?: string;
  last_seen_at?: string;
  days_on_market?: number;
  days_on_market_bucket?: string;
  price_drop_7d?: number;
  price_drop_30d?: number;
  snapshot_count: number;
};

type OfferTrendsBulkResponse = { trends: OfferTrendItem[] };
type OfferSearchResponse = { offers: DealerOffer[] };
type OfferRankResponse = { ranked_offers: RankedOffer[] };
type IngestFallbackResponse = {
  provider: string;
  jobs_collected: number;
  normalized_count: number;
  inserted: number;
  updated: number;
};

const apiBase = "http://localhost:8000";

const emptyDealerSite: DealerSiteInput = {
  dealer_id: "",
  dealer_name: "",
  dealer_zip: "",
  brand: "",
  site_url: "",
  inventory_url: "",
  adapter_key: "",
};

export function ComparisonPage() {
  const [userZip, setUserZip] = useState("18706");
  const [radiusMiles, setRadiusMiles] = useState(100);
  const [budgetOtd, setBudgetOtd] = useState(30000);
  const [make, setMake] = useState("Honda");
  const [model, setModel] = useState("Civic");
  const [year, setYear] = useState(2025);
  const [trim, setTrim] = useState("");
  const [dealerSites, setDealerSites] = useState<DealerSiteInput[]>([]);
  const [includeInTransit, setIncludeInTransit] = useState(true);
  const [includePreSold, setIncludePreSold] = useState(false);
  const [includeHidden, setIncludeHidden] = useState(false);

  const [offers, setOffers] = useState<DealerOffer[]>([]);
  const [rankedOffers, setRankedOffers] = useState<RankedOffer[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingRank, setLoadingRank] = useState(false);
  const [loadingIngest, setLoadingIngest] = useState(false);
  const [historyByKey, setHistoryByKey] = useState<Record<string, OfferHistoryResponse>>({});
  const [historyLoadingByKey, setHistoryLoadingByKey] = useState<Record<string, boolean>>({});
  const [historyErrorByKey, setHistoryErrorByKey] = useState<Record<string, string | null>>({});
  const [expandedHistoryKeys, setExpandedHistoryKeys] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);

  const targetPreview = useMemo(() => {
    const t = trim.trim();
    return `${year} ${make} ${model}${t ? ` ${t}` : ""}`;
  }, [year, make, model, trim]);

  function offerKey(offer: DealerOffer): string {
    return `${offer.dealership_id}::${offer.vehicle_id}`;
  }

  function formatSeenAt(value?: string): string {
    if (!value) {
      return "n/a";
    }
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) {
      return value;
    }
    return dt.toLocaleString();
  }

  function buildTargets(): VehicleTarget[] {
    return [
      {
        make: make.trim(),
        model: model.trim(),
        year,
        ...(trim.trim() ? { trim: trim.trim() } : {}),
      },
    ];
  }

  function buildDealerSites(): DealerSiteInput[] | undefined {
    const filtered = dealerSites
      .map((site) => ({
        dealer_id: site.dealer_id.trim(),
        dealer_name: site.dealer_name.trim(),
        dealer_zip: site.dealer_zip.trim(),
        brand: site.brand.trim(),
        site_url: site.site_url.trim(),
        inventory_url: site.inventory_url.trim(),
        adapter_key: site.adapter_key.trim().toLowerCase(),
      }))
      .filter(
        (site) =>
          site.dealer_id &&
          site.dealer_name &&
          site.dealer_zip &&
          site.brand &&
          site.site_url &&
          site.inventory_url &&
          site.adapter_key,
      );

    return filtered.length > 0 ? filtered : undefined;
  }

  function addDealerSite() {
    setDealerSites((prev) => [...prev, { ...emptyDealerSite }]);
  }

  function removeDealerSite(index: number) {
    setDealerSites((prev) => prev.filter((_, idx) => idx !== index));
  }

  function updateDealerSite(index: number, key: keyof DealerSiteInput, value: string) {
    setDealerSites((prev) => prev.map((item, idx) => (idx === index ? { ...item, [key]: value } : item)));
  }

  async function ingestFallback() {
    setLoadingIngest(true);
    setError(null);
    setIngestStatus(null);

    try {
      const response = await fetch(`${apiBase}/ingest/fallback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_zip: userZip.trim(),
          radius_miles: radiusMiles,
          budget_otd: budgetOtd,
          targets: buildTargets(),
          dealer_sites: buildDealerSites(),
        }),
      });

      if (!response.ok) {
        throw new Error(`Fallback ingest failed (${response.status})`);
      }

      const data = (await response.json()) as IngestFallbackResponse;
      setIngestStatus(
        `Ingested via ${data.provider}: jobs=${data.jobs_collected}, normalized=${data.normalized_count}, inserted=${data.inserted}, updated=${data.updated}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run fallback ingest agent");
    } finally {
      setLoadingIngest(false);
    }
  }

  async function rankOfferList(offersToRank: DealerOffer[]): Promise<RankedOffer[]> {
    const response = await fetch(`${apiBase}/offers/rank`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget_otd: budgetOtd, offers: offersToRank }),
    });

    if (!response.ok) {
      throw new Error(`Rank failed (${response.status})`);
    }

    const data = (await response.json()) as OfferRankResponse;
    return data.ranked_offers ?? [];
  }

  async function fetchTrendSignals(offersToEnrich: DealerOffer[]): Promise<DealerOffer[]> {
    if (offersToEnrich.length === 0) {
      return offersToEnrich;
    }

    const trendKeys: OfferTrendKey[] = offersToEnrich.map((offer) => ({
      dealership_id: offer.dealership_id,
      vehicle_id: offer.vehicle_id,
    }));

    const response = await fetch(`${apiBase}/offers/trends/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ offers: trendKeys }),
    });

    if (!response.ok) {
      return offersToEnrich;
    }

    const data = (await response.json()) as OfferTrendsBulkResponse;
    const trendByKey = new Map(
      (data.trends ?? []).map((item) => [`${item.dealership_id}::${item.vehicle_id}`, item]),
    );

    return offersToEnrich.map((offer) => {
      const trend = trendByKey.get(`${offer.dealership_id}::${offer.vehicle_id}`);
      if (!trend) {
        return offer;
      }
      return {
        ...offer,
        days_on_market: offer.days_on_market ?? trend.days_on_market,
        days_on_market_bucket: trend.days_on_market_bucket ?? offer.days_on_market_bucket,
        price_drop_7d: trend.price_drop_7d ?? offer.price_drop_7d,
        price_drop_30d: trend.price_drop_30d ?? offer.price_drop_30d,
      };
    });
  }

  async function loadOfferHistory(offer: DealerOffer): Promise<void> {
    const key = offerKey(offer);

    setHistoryLoadingByKey((prev) => ({ ...prev, [key]: true }));
    setHistoryErrorByKey((prev) => ({ ...prev, [key]: null }));

    try {
      const params = new URLSearchParams({
        dealership_id: offer.dealership_id,
        vehicle_id: offer.vehicle_id,
        limit: "180",
      });
      const response = await fetch(`${apiBase}/offers/history?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`History failed (${response.status})`);
      }

      const data = (await response.json()) as OfferHistoryResponse;
      setHistoryByKey((prev) => ({ ...prev, [key]: data }));
    } catch (err) {
      setHistoryErrorByKey((prev) => ({
        ...prev,
        [key]: err instanceof Error ? err.message : "Failed to load history",
      }));
    } finally {
      setHistoryLoadingByKey((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function toggleOfferHistory(offer: DealerOffer) {
    const key = offerKey(offer);
    const isExpanded = expandedHistoryKeys[key] === true;

    if (isExpanded) {
      setExpandedHistoryKeys((prev) => ({ ...prev, [key]: false }));
      return;
    }

    setExpandedHistoryKeys((prev) => ({ ...prev, [key]: true }));
    if (!historyByKey[key] && !historyLoadingByKey[key]) {
      await loadOfferHistory(offer);
    }
  }

  async function searchAndRankOffers() {
    setLoadingSearch(true);
    setLoadingRank(true);
    setError(null);
    setRankedOffers([]);
    setHistoryByKey({});
    setHistoryLoadingByKey({});
    setHistoryErrorByKey({});
    setExpandedHistoryKeys({});

    try {
      const response = await fetch(`${apiBase}/offers/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_zip: userZip.trim(),
          radius_miles: radiusMiles,
          budget_otd: budgetOtd,
          targets: buildTargets(),
          dealer_sites: buildDealerSites(),
          include_in_transit: includeInTransit,
          include_pre_sold: includePreSold,
          include_hidden: includeHidden,
        }),
      });

      if (!response.ok) {
        throw new Error(`Search failed (${response.status})`);
      }

      const data = (await response.json()) as OfferSearchResponse;
      const nextOffers = data.offers ?? [];

      if (nextOffers.length === 0) {
        setOffers([]);
        setRankedOffers([]);
        return;
      }

      const enrichedOffers = await fetchTrendSignals(nextOffers);
      setOffers(enrichedOffers);

      const ranked = await rankOfferList(enrichedOffers);
      setRankedOffers(ranked);
    } catch (err) {
      setOffers([]);
      setRankedOffers([]);
      setError(err instanceof Error ? err.message : "Failed to search and rank offers");
    } finally {
      setLoadingSearch(false);
      setLoadingRank(false);
    }
  }

  async function rerankCurrentOffers() {
    if (offers.length === 0) {
      setError("Search offers first, then re-rank them.");
      return;
    }

    setLoadingRank(true);
    setError(null);

    try {
      const ranked = await rankOfferList(offers);
      setRankedOffers(ranked);
    } catch (err) {
      setRankedOffers([]);
      setError(err instanceof Error ? err.message : "Failed to rank offers");
    } finally {
      setLoadingRank(false);
    }
  }

  function renderHistoryPanel(offer: DealerOffer) {
    const key = offerKey(offer);
    const expanded = expandedHistoryKeys[key] === true;
    const loading = historyLoadingByKey[key] === true;
    const response = historyByKey[key];
    const fetchError = historyErrorByKey[key];

    return (
      <div className="history-wrap">
        <button className="btn" type="button" onClick={() => void toggleOfferHistory(offer)}>
          {expanded ? "Hide Price History" : "View Price History"}
        </button>

        {expanded && (
          <div className="history-panel">
            {loading && <p className="empty">Loading history...</p>}
            {!loading && fetchError && <p className="error">{fetchError}</p>}
            {!loading && !fetchError && response && (
              <>
                <div className="stats history-meta">
                  <span>First Seen: {formatSeenAt(response.first_seen_at)}</span>
                  <span>Last Seen: {formatSeenAt(response.last_seen_at)}</span>
                  {response.days_on_market !== undefined && <span>Tracked DOM: {response.days_on_market}d</span>}
                </div>
                {response.points.length === 0 ? (
                  <p className="empty">No historical snapshots yet.</p>
                ) : (
                  <ul className="history-list">
                    {response.points.map((point, idx) => (
                      <li key={`${key}-${idx}`}>
                        <span>{formatSeenAt(point.seen_at)}</span>
                        <span>${point.otd_price.toLocaleString()}</span>
                        <span>{point.data_provider ?? "n/a"}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="comparison-page">
      <section className="hero">
        <p className="kicker">AutoHaggle</p>
        <h1>Find and rank dealer offers before negotiation</h1>
        <p className="subtitle">
          Search live listings, include incoming/hidden inventory if needed, and rank by price, specs, and fees.
        </p>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Vehicle Search</h2>
          <span className="pill">Target: {targetPreview}</span>
        </div>

        <div className="form-grid">
          <label>
            ZIP Code
            <input value={userZip} onChange={(e) => setUserZip(e.target.value)} placeholder="18706" />
          </label>
          <label>
            Radius (miles)
            <input
              type="number"
              min={1}
              max={250}
              value={radiusMiles}
              onChange={(e) => setRadiusMiles(Number(e.target.value) || 1)}
            />
          </label>
          <label>
            Budget OTD ($)
            <input
              type="number"
              min={1}
              value={budgetOtd}
              onChange={(e) => setBudgetOtd(Number(e.target.value) || 1)}
            />
          </label>
          <label>
            Make
            <input value={make} onChange={(e) => setMake(e.target.value)} placeholder="Honda" />
          </label>
          <label>
            Model
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="Civic" />
          </label>
          <label>
            Year
            <input
              type="number"
              min={1990}
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || 2025)}
            />
          </label>
          <label className="wide">
            Trim (optional)
            <input value={trim} onChange={(e) => setTrim(e.target.value)} placeholder="EX / Sport / XLE" />
          </label>
        </div>

        <div className="toggles">
          <label className="toggle">
            <input type="checkbox" checked={includeInTransit} onChange={(e) => setIncludeInTransit(e.target.checked)} />
            Include In-Transit
          </label>
          <label className="toggle">
            <input type="checkbox" checked={includePreSold} onChange={(e) => setIncludePreSold(e.target.checked)} />
            Include Pre-Sold
          </label>
          <label className="toggle">
            <input type="checkbox" checked={includeHidden} onChange={(e) => setIncludeHidden(e.target.checked)} />
            Include Hidden Inventory
          </label>
        </div>

        <div className="actions">
          <button className="btn primary" onClick={searchAndRankOffers} disabled={loadingSearch || loadingRank}>
            {loadingSearch || loadingRank ? "Searching + Ranking..." : "Search + Rank Offers"}
          </button>
          <button className="btn" onClick={rerankCurrentOffers} disabled={loadingRank || offers.length === 0}>
            {loadingRank ? "Ranking..." : "Re-rank Current"}
          </button>
          <button className="btn" onClick={ingestFallback} disabled={loadingIngest}>
            {loadingIngest ? "Ingesting..." : "Run Parser Agent"}
          </button>
          <a className="btn link" href="/?view=warroom&sessionId=replace-with-session-id">
            Open War Room
          </a>
        </div>

        <div className="panel" style={{ marginTop: 12 }}>
          <div className="panel-header">
            <h2>Dealer Sites (Optional)</h2>
            <button className="btn" onClick={addDealerSite} type="button">
              + Add Dealer Site
            </button>
          </div>
          {dealerSites.length === 0 ? (
            <p className="empty">No dealer sites configured. API/default sources will be used.</p>
          ) : (
            <div className="offer-list">
              {dealerSites.map((site, idx) => (
                <div className="offer-card" key={`dealer-site-${idx}`}>
                  <div className="form-grid">
                    <label>
                      Dealer ID
                      <input value={site.dealer_id} onChange={(e) => updateDealerSite(idx, "dealer_id", e.target.value)} />
                    </label>
                    <label>
                      Dealer Name
                      <input value={site.dealer_name} onChange={(e) => updateDealerSite(idx, "dealer_name", e.target.value)} />
                    </label>
                    <label>
                      Dealer ZIP
                      <input value={site.dealer_zip} onChange={(e) => updateDealerSite(idx, "dealer_zip", e.target.value)} />
                    </label>
                    <label>
                      Brand
                      <input value={site.brand} onChange={(e) => updateDealerSite(idx, "brand", e.target.value)} placeholder="Honda/Toyota" />
                    </label>
                    <label>
                      Adapter Key
                      <input value={site.adapter_key} onChange={(e) => updateDealerSite(idx, "adapter_key", e.target.value)} placeholder="honda/toyota" />
                    </label>
                    <label>
                      Site URL
                      <input value={site.site_url} onChange={(e) => updateDealerSite(idx, "site_url", e.target.value)} placeholder="https://dealer.example" />
                    </label>
                    <label className="wide">
                      Inventory URL
                      <input value={site.inventory_url} onChange={(e) => updateDealerSite(idx, "inventory_url", e.target.value)} placeholder="https://dealer.example/new-inventory" />
                    </label>
                  </div>
                  <div className="actions" style={{ marginTop: 8 }}>
                    <button className="btn" type="button" onClick={() => removeDealerSite(idx)}>
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {ingestStatus && <p className="success">{ingestStatus}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="results-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Search Results</h2>
            <span className="pill">{offers.length} offers</span>
          </div>

          {offers.length === 0 ? (
            <p className="empty">No offers yet. Run a search to populate your shortlist.</p>
          ) : (
            <div className="offer-list">
              {offers.map((offer) => (
                <div className="offer-card" key={offer.offer_id}>
                  <div className="offer-head">
                    <strong>{offer.vehicle_label}</strong>
                    <span>${offer.otd_price.toLocaleString()}</span>
                  </div>
                  <p>{offer.dealership_name}</p>
                  <div className="stats">
                    <span>{offer.distance_miles} mi</span>
                    <span>Fees ${offer.fees.toLocaleString()}</span>
                    <span>Adj. ${offer.market_adjustment.toLocaleString()}</span>
                    <span>Specs {offer.specs_score}/100</span>
                    {offer.days_on_market !== undefined && (
                      <span>
                        DOM {offer.days_on_market}d ({offer.days_on_market_source ?? "n/a"})
                      </span>
                    )}
                    {offer.days_on_market_bucket && <span>DOM Bucket {offer.days_on_market_bucket}</span>}
                    {offer.price_drop_7d !== undefined && offer.price_drop_7d > 0 && (
                      <span>Drop 7d ${offer.price_drop_7d.toLocaleString()}</span>
                    )}
                    {offer.price_drop_30d !== undefined && offer.price_drop_30d > 0 && (
                      <span>Drop 30d ${offer.price_drop_30d.toLocaleString()}</span>
                    )}
                    {offer.inventory_status && <span>Status {offer.inventory_status}</span>}
                    {offer.is_in_transit && <span className="tag">In-Transit</span>}
                    {offer.is_pre_sold && <span className="tag">Pre-Sold</span>}
                    {offer.is_hidden && <span className="tag">Hidden</span>}
                    {offer.data_provider && <span>Provider {offer.data_provider}</span>}
                  </div>
                  <div className="link-actions">
                    {offer.listing_url && (
                      <a className="btn link" href={offer.listing_url} target="_blank" rel="noreferrer">
                        Open Listing
                      </a>
                    )}
                    {offer.dealer_url && (
                      <a className="btn link" href={offer.dealer_url} target="_blank" rel="noreferrer">
                        Dealer Site
                      </a>
                    )}
                  </div>
                  {renderHistoryPanel(offer)}
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Ranked Shortlist</h2>
            <span className="pill">{rankedOffers.length} ranked</span>
          </div>

          {rankedOffers.length === 0 ? (
            <p className="empty">Ranked results appear automatically after Search + Rank Offers.</p>
          ) : (
            <div className="offer-list">
              {rankedOffers.map((item) => (
                <div className={`rank-card${item.rank === 1 ? " best" : ""}`} key={`${item.offer.offer_id}-${item.rank}`}>
                  <div className="rank-row">
                    <span className="rank">#{item.rank}</span>
                    <strong>{item.offer.dealership_name}</strong>
                    <span className="score">Score {item.score}</span>
                  </div>
                  {item.rank === 1 && <div className="best-pill">Best Deal</div>}
                  <p>{item.offer.vehicle_label}</p>
                  <div className="scorebar-wrap">
                    <div className="scorebar" style={{ width: `${Math.min(item.score, 100)}%` }} />
                  </div>
                  <div className="stats">
                    <span>OTD ${item.offer.otd_price.toLocaleString()}</span>
                    <span>Price {item.score_breakdown.price_score ?? 0}</span>
                    <span>Specs {item.score_breakdown.specs_score ?? 0}</span>
                    <span>Fees {item.score_breakdown.fee_score ?? 0}</span>
                    {item.offer.days_on_market !== undefined && <span>DOM {item.offer.days_on_market}d</span>}
                    {item.offer.days_on_market_bucket && <span>DOM Bucket {item.offer.days_on_market_bucket}</span>}
                    {item.offer.price_drop_7d !== undefined && item.offer.price_drop_7d > 0 && (
                      <span>Drop 7d ${item.offer.price_drop_7d.toLocaleString()}</span>
                    )}
                    {item.offer.price_drop_30d !== undefined && item.offer.price_drop_30d > 0 && (
                      <span>Drop 30d ${item.offer.price_drop_30d.toLocaleString()}</span>
                    )}
                    <span>Trend {item.score_breakdown.trend_score ?? 0}</span>
                  </div>
                  <div className="link-actions">
                    {item.offer.listing_url && (
                      <a className="btn link" href={item.offer.listing_url} target="_blank" rel="noreferrer">
                        Open Listing
                      </a>
                    )}
                    {item.offer.dealer_url && (
                      <a className="btn link" href={item.offer.dealer_url} target="_blank" rel="noreferrer">
                        Dealer Site
                      </a>
                    )}
                  </div>
                  {renderHistoryPanel(item.offer)}
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}














