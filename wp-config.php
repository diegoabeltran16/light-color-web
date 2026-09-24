<?php
/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the website, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'belleza' );

/** Database username */
define( 'DB_USER', 'root' );

/** Database password */
define( 'DB_PASSWORD', 'root' );

/** Database hostname */
define( 'DB_HOST', 'localhost:8889' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8mb4' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */

define('AUTH_KEY',         '`TrIy/G-^P}bUL~+4/~L}|7cV5kCaQI(@&cK2?q8N-C/KBY06r]!u|r&Xm(WLZ7_');
define('SECURE_AUTH_KEY',  ';b6Rvw/ol,tZYA@P@[c-{FH`96x-&o:_+iep|F9*Nz}to`i-nj.72waBV_H|c*V;');
define('LOGGED_IN_KEY',    'w@(nKpD2PrRT~Q5pps-gFoe!|6D9Ox&}66my,UJZU?P-:ZFLS<bnMUj}GG2-2`6+');
define('NONCE_KEY',        '#ddwmrwrTEP(8H!Z[!Jv)E&`c|Z&GMXwWwpb$_Pa%GQhDGdW9n[gc^YK+/LIZsFC');
define('AUTH_SALT',        ' +|:x?lE:rHI241-7uf#>U0*v;TRt~1 snlKogoj-3Sv5v6I*B?7V(dD>ESi^WIy');
define('SECURE_AUTH_SALT', ';r)j@+gI&H8Mhf;u`riezwFx2 1_#Ei62(RN< 6[N[cC~}C|3)X[K,1oDvj,L:zc');
define('LOGGED_IN_SALT',   '?q[#T}- na{l{%L+p3jui- 1-F(#<rg1E-f>uL{?}(f|C5W*o.KeJv`Uccw(sALQ');
define('NONCE_SALT',       '.kQSW}w9(N>*##81/|>kFM26N@|Rnb{qF|>VXh+Y{GLQ09oT`!zsYrfT~M,- ecu');

/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 *
 * At the installation time, database tables are created with the specified prefix.
 * Changing this value after WordPress is installed will make your site think
 * it has not been installed.
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/#table-prefix
 */
$table_prefix = 'wp_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://developer.wordpress.org/advanced-administration/debug/debug-wordpress/
 */
define( 'WP_DEBUG', false );

/* Add any custom values between this line and the "stop editing" line. */



/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';
