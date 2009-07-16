{# included into articlebox #}
{% if not tweet.is_retweet %}
	<div class="tweet">
		{%if article.url %}
		&ldquo;<a href="{{article.url|escape}}">{{tweet.text|escape}}</a>&rdquo;
		{% else %}
			&ldquo;{{tweet.text|escape}}&rdquo;
		{% endif %}
		{%if admin%}
			<a class="admin" href="/admin/datastore/edit?key={{tweet.key}}&amp;kind=Tweet&amp;next={{refresh_url|urlencode}}">e</a>
			<a class="admin" href="/do/index-tweet?key={{tweet.key}}">r</a>
		{%endif%}
		<div class="tweeter">
			<a href="/tweeter/{{tweet.from_user|urlencode}}{{q}}">{{tweet.from_user}}</a>
			<a class="tau" href="http://twitter.com/{{tweet.from_user}}/status/{{tweet.id}}">#</a>
		</div>
	</div>
{% endif %}
