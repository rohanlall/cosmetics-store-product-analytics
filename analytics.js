// Thin analytics wrapper: sends to PostHog (if configured) and always logs locally.
(function () {
  const cfg = window.ANALYTICS_CONFIG || {};
  const LS_KEY = "pa_events";

  function uid() {
    let id = localStorage.getItem("pa_uid");
    if (!id) { id = "u_" + Math.random().toString(36).slice(2, 10); localStorage.setItem("pa_uid", id); }
    return id;
  }
  function session() {
    let s = sessionStorage.getItem("pa_sid");
    if (!s) { s = "s_" + Date.now().toString(36); sessionStorage.setItem("pa_sid", s); }
    return s;
  }

  if (cfg.POSTHOG_KEY) {
    // Official PostHog snippet loader
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    posthog.init(cfg.POSTHOG_KEY, { api_host: cfg.POSTHOG_HOST, person_profiles: "identified_only", capture_pageview: true, autocapture: true });
    posthog.identify(uid());
  }

  window.track = function (event, props = {}) {
    const e = { event, props, user: uid(), session: session(), ts: Date.now(), path: location.pathname };
    const all = JSON.parse(localStorage.getItem(LS_KEY) || "[]");
    all.push(e);
    localStorage.setItem(LS_KEY, JSON.stringify(all));
    if (cfg.POSTHOG_KEY && window.posthog) posthog.capture(event, props);
    console.debug("[track]", event, props);
  };
  window.getLocalEvents = () => JSON.parse(localStorage.getItem(LS_KEY) || "[]");
  window.clearLocalEvents = () => localStorage.removeItem(LS_KEY);
})();
