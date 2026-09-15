# Custom domain switch plan

The custom domains are registered but deliberately inactive while the Blogger API appeal is unresolved.

## Registered domains

- UK: `worthbuyinguk.co.uk` -> planned Blogger hostname `www.worthbuyinguk.co.uk`
- US: `worthbuyingusa.com` -> planned Blogger hostname `www.worthbuyingusa.com`

## Current safe state

`automation/domains.json` has `active: "blogspot"` for both markets and `custom_domain_connected_to_blogger: false`.

Pinterest feed and image generators read the active hostname through `src/site_config.py`, so they continue to use the existing Blogspot domains today.

The helper refuses to activate a custom domain unless `custom_domain_connected_to_blogger` is also true. This is an intentional safety gate.

## Migration order after Blogger API access is restored

1. Migrate one market at a time, starting with USA.
2. Configure the Blogger custom domain and Cloudflare DNS records.
3. Enable Blogger HTTPS and root-domain redirect.
4. Confirm old Blogspot URLs redirect to the matching custom-domain URLs.
5. Test a sample live article and confirm Blogger API publishing still works.
6. Set `custom_domain_connected_to_blogger` to `true` for that market in `automation/domains.json`.
7. Change that market's `active` value from `blogspot` to `custom`.
8. Regenerate Pinterest images/feed so branding moves to the custom hostname.
9. Confirm X/Buffer uses the live URL returned by Blogger.
10. Update Amazon Associates, eBay/EPN, Search Console and other external site records where appropriate.
11. Repeat for the other market after the first migration is stable.

Do not flip the `active` setting before the corresponding Blogger custom-domain connection has been tested.
