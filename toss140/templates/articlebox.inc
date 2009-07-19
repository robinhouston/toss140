{% if article.date %}
	<div class="articlebox">
		{% ifchanged article.date %}
			<div class="date">
				{% if date_prev %}
					<a
						title="{{ date_prev|date:"D jS F Y" }}"
						href="/date/{{ date_prev }}{{q}}">←</a>
				{% endif %}
				<a href="/date/{{ article.date }}{{q}}">{{ article.date|date:"D jS F Y" }}</a>
				{% if date_next %}
					<a
						title="{{ date_next|date:"D jS F Y" }}"
						href="/date/{{ date_next }}{{q}}">→</a>
				{% endif %}
			</div>
		{% endifchanged %}
		{% for tweet in article.tweets %}
			{% include "tweet.inc" %}
		{% endfor %}
		<div class="author">
			– {%if article.author%}
					<a
						href="/author/{{ article.author|urlencode }}{{q}}"
						>{{ article.author|escape }}</a>,
				{%else%}
					author unknown,
				{%endif%}
			<a
				href="/organ/{{ article.parent.name|urlencode }}{{q}}"
				>{{ article.parent.name|escape }}</a>
			{%if admin%}
				<a class="admin"
					href="/admin/datastore/edit?key={{ article.key }}&amp;kind=Article&amp;next={{ refresh_url|urlencode }}"
					>e</a>
			{%endif%}
		</div>
	</div>
{% endif %}