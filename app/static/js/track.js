/* G1 — funnel/analytics tracking.
   Fires Umami custom events (analytics.negar.io) AND a local beacon to /api/track
   so the in-app admin funnel dashboard has real data even if Umami is blocked. */
(function(){
  if (window.__trackLoaded) return;
  window.__trackLoaded = true;

  window.FUNNEL_EVENTS = ["page_view_landing","birth_form_start","birth_form_submit","chart_created","chart_view_scroll_50","preview_insight_viewed","explore_card_click","explore_free_used","signup_started","signup_completed","chart_claimed","credit_cta_shown","credit_cta_click","pack_selected","checkout_started","payment_success","payment_failed","credit_spent","report_started","report_completed","report_pdf_download","transit_forecast_view","transit_analyze_purchase","chat_first_message","share_clicked","referral_link_copied"];

  function sid(){
    try{
      var s = localStorage.getItem('sid');
      if(!s){ s = 's' + Math.random().toString(36).slice(2,10) + Date.now().toString(36); localStorage.setItem('sid', s); }
      return s;
    }catch(e){ return 'sid'; }
  }

  window.track = function(event, props){
    props = props || {};
    // Umami custom event
    try{ if(window.umami && typeof umami.track === 'function'){ umami.track(event, props); } }catch(e){}
    // self-contained local beacon -> /api/track
    try{
      var payload = { event: event, session_id: sid(), path: location.pathname, ref: props.__ref || '', props: JSON.stringify(props) };
      if(navigator.sendBeacon){ navigator.sendBeacon('/api/track', new Blob([JSON.stringify(payload)], {type:'application/json'})); }
      else { fetch('/api/track', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload), keepalive:true}); }
    }catch(e){}
  };

  // auto-wire [data-track] click handlers (no inline JS)
  document.addEventListener('click', function(e){
    var el = e.target.closest('[data-track]');
    if(!el) return;
    var ev = el.getAttribute('data-track');
    if(ev){ window.track(ev, {__ref: el.getAttribute('data-ref') || ''}); }
  });

  // page_view_landing auto-fires on landing page (data-page="landing")
  var body = document.body;
  if(body && body.getAttribute('data-page') === 'landing'){
    setTimeout(function(){ window.track('page_view_landing', {__ref: new URLSearchParams(location.search).get('ref') || ''}); }, 200);
  }

  // G1: birth_form_start — first interaction on the birth form
  var bf = document.getElementById('birthForm');
  if (bf){
    var started = false;
    var fireStart = function(){ if (started) return; started = true; window.track('birth_form_start'); };
    bf.addEventListener('input', fireStart, {once:true});
    bf.addEventListener('change', fireStart, {once:true});
  }
})();
