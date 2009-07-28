{# included into articlebox #}
<div class="tweet">
	{%if article.url %}
	&ldquo;<a href="{{ article.url|escape }}"
		title="{{ article.title|escape }}"
		onclick="javascript:pageTracker._trackPageview('/outbound/from_text/{{ tweet.key.name }}');"
		>{{tweet.text|escape}}</a>&rdquo;
	{% else %}
		&ldquo;{{tweet.text|escape}}&rdquo;
	{% endif %}
	{%if admin%}
		<a class="admin"
			href="/admin/datastore/edit?key={{ tweet.key }}&amp;kind=Tweet&amp;next={{ refresh_url|urlenc_uni }}">e</a>
		<a class="admin" href="/do/index-tweet?key={{ tweet.key }}">r</a>
	{%endif%}
	<a class="rt" onclick="javascript:document.rt{{ tweet.key }}.submit()" href="#retweet">RT</a>
	<div class="tweeter">
		<a title="All summaries by {{ tweet.from_user|escape }}"
			href="/tweeter/{{ tweet.from_user|urlenc_uni }}{{q}}"
			>{{ tweet.from_user|escape }}</a>
		<a class="tau"
			title="This summary on Twitter"
			onclick="javascript:pageTracker._trackPageview('/outbound/status/{{ tweet.id }}');"
			href="http://twitter.com/{{ tweet.from_user }}/status/{{ tweet.id }}">#</a>
	</div>
	<form name="rt{{ tweet.key }}" method="POST" action="/rt/{{ tweet.key|urlenc_uni }}"></form>
</div>
